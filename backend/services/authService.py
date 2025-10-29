from backend.data.database import db


class AuthService:
    @staticmethod
    def authenticate_doctor(email, password):
        doctor = db.get_doctor_by_email(email)
        
        if not doctor:
            return None, "Doctor not found"
        
        if doctor['password'] != password:
            return None, "Invalid password"

        safe_doctor = {k: v for k, v in doctor.items() if k != 'password'}
        
        return safe_doctor, None

    @staticmethod
    def validate_session(doctor_id):
        return True

    @staticmethod
    def logout_doctor(doctor_id):
        return True