from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------
# INSTANCIA DE SQLAlchemy
# ------------------------
db = SQLAlchemy()


# ============================================================
# 1. MODELO: FACULTADES
# ============================================================
class Faculty(db.Model):
    __tablename__ = 'faculties'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    domain = Column(String(120), nullable=False)  # ej: "cucea.udg.mx"
    color_theme = Column(String(20), default="#003366")  # Identidad visual UDG
    
    users = relationship('User', back_populates='faculty', cascade='all, delete')
    chat_rooms = relationship('ChatRoom', backref='faculty', cascade='all, delete')


# ============================================================
# 2. MODELO: USUARIOS
# ============================================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='Usuario')  # Administrador / Moderador / Usuario
    faculty_id = Column(Integer, ForeignKey('faculties.id'), nullable=True)
    
    profile_image = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    faculty = relationship('Faculty', back_populates='users')
    messages = relationship('Message', back_populates='sender', cascade='all, delete')

    # Logs donde el usuario es afectado
    moderation_logs = relationship(
        'ModerationLog',
        back_populates='user',
        cascade='all, delete',
        foreign_keys='ModerationLog.user_id'
    )

    # Logs donde el usuario actuó como moderador
    moderated_logs = relationship(
        'ModerationLog',
        back_populates='moderator',
        cascade='all, delete',
        foreign_keys='ModerationLog.moderator_id'
    )

    sessions = relationship('UserSession', back_populates='user', cascade='all, delete')
    notifications = relationship('Notification', backref='user', cascade='all, delete')

    # --- Métodos de utilidad ---
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'role': self.role,
            'faculty': self.faculty.name if self.faculty else None,
            'profile_image': self.profile_image,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat()
        }

# ============================================================
# 3. MODELO: SALAS DE CHAT
# ============================================================
class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    is_global = Column(Boolean, default=False)
    faculty_id = Column(Integer, ForeignKey('faculties.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship('Message', back_populates='room', cascade='all, delete')


# ============================================================
# 4. MODELO: MENSAJES
# ============================================================
class Message(db.Model):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    sender_id = Column(Integer, ForeignKey('users.id'))
    room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    
    is_flagged = Column(Boolean, default=False)  # Detección automática de contenido inapropiado
    flagged_reason = Column(String(255), nullable=True)
    
    sender = relationship('User', back_populates='messages')
    room = relationship('ChatRoom', back_populates='messages')


# ============================================================
# 5. MODELO: REGISTRO DE MODERACIÓN
# ============================================================
class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))  # Usuario afectado
    moderator_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Moderador que actuó
    action = Column(String(120), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = relationship('User', back_populates='moderation_logs', foreign_keys=[user_id])
    moderator = relationship('User', back_populates='moderated_logs', foreign_keys=[moderator_id])


# ============================================================
# 6. MODELO: PALABRAS PROHIBIDAS / CONTEXTO ACADÉMICO
# ============================================================
class BannedWord(db.Model):
    __tablename__ = 'banned_words'
    
    id = Column(Integer, primary_key=True)
    word = Column(String(100), nullable=False, unique=True)
    severity = Column(String(20), default='leve')  # leve, moderado, grave
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# 7. MODELO: NOTIFICACIONES
# ============================================================
class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String(120), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# 8. MODELO: SESIONES DE USUARIO
# ============================================================
class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    jwt_token = Column(Text, nullable=False)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    user = relationship('User', back_populates='sessions')


# ============================================================
# 9. MODELO: AUDITORÍA
# ============================================================
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    action = Column(String(255), nullable=False)
    performed_by = Column(String(150), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text, nullable=True)
