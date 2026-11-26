import React, { useMemo } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { Users, CheckCircle, BarChart3, Clock } from 'lucide-react';
import StatusBadge from '../patients/StatusBadge';
import Avatar from '../common/Avatar';
import LoadError from '../common/LoadError';
import { Skeleton, StatCardSkeleton } from '../common/Skeleton';
import { formatDate, isThisMonth } from '../../lib/format';

const RECENT_COUNT = 5;

export function computeStats(patients) {
  // Average only over real AI results: unsegmented and simulated patients have no
  // meaningful confidence.
  const scored = patients.filter(p => p.status === 'completed' && !p.simulated);
  return {
    totalPatients: patients.length,
    completed: patients.filter(p => p.status === 'completed').length,
    avgConfidence: scored.length > 0
      ? `${(scored.reduce((sum, p) => sum + (p.confidence || 0), 0) / scored.length * 100).toFixed(1)}%`
      : '—',
    thisMonth: patients.filter(p => isThisMonth(p.date)).length,
  };
}

function StatCard({ icon: Icon, tint, label, value }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
      <div className={`w-12 h-12 ${tint} rounded-lg flex items-center justify-center mb-4`}>
        <Icon className="w-6 h-6" aria-hidden="true" />
      </div>
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className="text-3xl font-bold text-white">{value}</p>
    </div>
  );
}

function DashboardView() {
  const { patients, loading, loadError, reloadPatients } = useOutletContext();
  const stats = useMemo(() => computeStats(patients), [patients]);
  // ISO dates sort correctly as strings.
  const recent = useMemo(
    () => [...patients].sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, RECENT_COUNT),
    [patients]
  );

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">Dashboard</h2>
        <p className="text-gray-400">Overview of your patients and segmentations</p>
      </div>

      {loadError && <LoadError message={loadError} onRetry={() => reloadPatients()} />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {loading ? (
          [0, 1, 2, 3].map(i => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard icon={Users} tint="bg-blue-600/20 text-blue-400" label="Total patients" value={stats.totalPatients} />
            <StatCard icon={CheckCircle} tint="bg-green-600/20 text-green-400" label="Completed segmentations" value={stats.completed} />
            <StatCard icon={BarChart3} tint="bg-purple-600/20 text-purple-400" label="Average confidence" value={stats.avgConfidence} />
            <StatCard icon={Clock} tint="bg-orange-600/20 text-orange-400" label="Scanned this month" value={stats.thisMonth} />
          </>
        )}
      </div>

      <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white">Recent patients</h3>
          <Link to="/patients" className="text-sm text-blue-400 hover:text-blue-300">View all</Link>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[0, 1, 2].map(i => <Skeleton key={i} className="h-[72px] rounded-lg" />)}
          </div>
        ) : recent.length === 0 ? (
          <p className="text-gray-400 text-center py-8">No patients yet</p>
        ) : (
          <ul className="space-y-3">
            {recent.map(patient => (
              <li key={patient.id}>
                <Link
                  to={`/patients/${patient.id}`}
                  className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition"
                >
                  <div className="flex items-center gap-4">
                    <Avatar name={patient.name} size="sm" />
                    <div>
                      <p className="font-medium text-white">{patient.name}</p>
                      <p className="text-sm text-gray-400">
                        {patient.age} years • {formatDate(patient.date)}
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={patient.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default DashboardView;
