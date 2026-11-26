import React from 'react';

/** A grey placeholder block shown while content loads. */
export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded bg-gray-700 ${className}`} />;
}

export function StatCardSkeleton() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
      <Skeleton className="w-12 h-12 rounded-lg mb-4" />
      <Skeleton className="w-24 h-4 mb-2" />
      <Skeleton className="w-16 h-8" />
    </div>
  );
}

export function PatientCardSkeleton() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <Skeleton className="w-12 h-12 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="w-32 h-4" />
          <Skeleton className="w-16 h-3" />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton className="w-full h-3" />
        <Skeleton className="w-full h-3" />
      </div>
    </div>
  );
}
