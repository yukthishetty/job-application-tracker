import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    create_engine,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    Float,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./jobtracker.db",
)

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "change-this-secret-in-production",
)

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


# =========================================================
# DATABASE MODELS
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    applications = relationship(
        "Application",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    interviews = relationship(
        "Interview",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    resumes = relationship(
        "Resume",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    user = relationship(
        "User",
        back_populates="resumes",
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    company: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    job_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    salary: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="Applied",
        nullable=False,
    )

    application_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    follow_up_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    resume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resumes.id"),
        nullable=True,
    )

    job_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship(
        "User",
        back_populates="applications",
    )


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("applications.id"),
        nullable=True,
    )

    company: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    interview_type: Mapped[str] = mapped_column(
        String(100),
        default="Technical",
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    meeting_link: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="interviews",
    )


Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Job Application Tracker API",
    description=(
        "Backend API for managing job and internship applications."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE DEPENDENCY
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================================================
# AUTHENTICATION
# =========================================================

password_hash = PasswordHash.recommended()


def create_access_token(user_id: int) -> str:
    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_authenticated_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format.",
        )

    token = authorization.split(
        " ",
        1,
    )[1].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token.",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token.",
            )

        user = db.get(
            User,
            int(user_id),
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found.",
            )

        return user

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        )

    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token.",
        )


# =========================================================
# REQUEST SCHEMAS
# =========================================================

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ApplicationRequest(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    job_type: Optional[str] = None
    salary: Optional[float] = None
    status: str = "Applied"
    application_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    resume_id: Optional[int] = None
    job_description: Optional[str] = None
    notes: Optional[str] = None


class InterviewRequest(BaseModel):
    company: str
    role: str
    interview_type: str = "Technical"
    scheduled_at: datetime
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    application_id: Optional[int] = None


# =========================================================
# BASIC ROUTES
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Job Application Tracker API is running!",
        "status": "success",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
    }


# =========================================================
# SIGNUP
# =========================================================

@app.post("/auth/signup")
def signup(
    data: SignupRequest,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists.",
        )

    if len(data.name.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid name.",
        )

    if len(data.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters.",
        )

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=password_hash.hash(
            data.password
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        user.id
    )

    return {
        "message": "Account created successfully.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        },
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/auth/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    try:
        valid_password = password_hash.verify(
            data.password,
            user.password_hash,
        )
    except Exception:
        valid_password = False

    if not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    token = create_access_token(
        user.id
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        },
    }


# =========================================================
# CURRENT USER
# =========================================================

@app.get("/me")
def get_me(
    user: User = Depends(
        get_authenticated_user
    ),
):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }


# =========================================================
# APPLICATION HELPER
# =========================================================

def application_to_dict(
    application: Application,
):
    return {
        "id": application.id,
        "company": application.company,
        "role": application.role,
        "location": application.location,
        "job_type": application.job_type,
        "salary": application.salary,
        "status": application.status,
        "application_date": application.application_date,
        "deadline": application.deadline,
        "follow_up_date": application.follow_up_date,
        "resume_id": application.resume_id,
        "job_description": application.job_description,
        "notes": application.notes,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


# =========================================================
# CREATE APPLICATION
# =========================================================

@app.post("/applications")
def create_application(
    data: ApplicationRequest,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    if data.resume_id:
        resume = (
            db.query(Resume)
            .filter(
                Resume.id == data.resume_id,
                Resume.user_id == user.id,
            )
            .first()
        )

        if not resume:
            raise HTTPException(
                status_code=404,
                detail="Selected resume was not found.",
            )

    application = Application(
        user_id=user.id,
        company=data.company.strip(),
        role=data.role.strip(),
        location=data.location,
        job_type=data.job_type,
        salary=data.salary,
        status=data.status,
        application_date=(
            data.application_date
            or datetime.utcnow()
        ),
        deadline=data.deadline,
        follow_up_date=data.follow_up_date,
        resume_id=data.resume_id,
        job_description=data.job_description,
        notes=data.notes,
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    return application_to_dict(
        application
    )


# =========================================================
# GET APPLICATIONS
# =========================================================

@app.get("/applications")
def get_applications(
    search: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Application)
        .filter(
            Application.user_id == user.id
        )
    )

    if search:
        search_text = f"%{search.strip()}%"

        query = query.filter(
            (Application.company.ilike(search_text))
            |
            (Application.role.ilike(search_text))
            |
            (Application.location.ilike(search_text))
        )

    if status:
        query = query.filter(
            Application.status == status
        )

    applications = (
        query
        .order_by(
            Application.created_at.desc()
        )
        .all()
    )

    return [
        application_to_dict(item)
        for item in applications
    ]


# =========================================================
# UPDATE APPLICATION
# =========================================================

@app.put("/applications/{application_id}")
def update_application(
    application_id: int,
    data: ApplicationRequest,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.user_id == user.id,
        )
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found.",
        )

    if data.resume_id:
        resume = (
            db.query(Resume)
            .filter(
                Resume.id == data.resume_id,
                Resume.user_id == user.id,
            )
            .first()
        )

        if not resume:
            raise HTTPException(
                status_code=404,
                detail="Selected resume was not found.",
            )

    application.company = data.company.strip()
    application.role = data.role.strip()
    application.location = data.location
    application.job_type = data.job_type
    application.salary = data.salary
    application.status = data.status
    application.application_date = (
        data.application_date
        or application.application_date
    )
    application.deadline = data.deadline
    application.follow_up_date = data.follow_up_date
    application.resume_id = data.resume_id
    application.job_description = data.job_description
    application.notes = data.notes

    db.commit()
    db.refresh(application)

    return application_to_dict(
        application
    )


# =========================================================
# DELETE APPLICATION
# =========================================================

@app.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.user_id == user.id,
        )
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found.",
        )

    db.delete(application)
    db.commit()

    return {
        "message": "Application deleted successfully."
    }


# =========================================================
# INTERVIEW HELPER
# =========================================================

def interview_to_dict(
    interview: Interview,
):
    return {
        "id": interview.id,
        "company": interview.company,
        "role": interview.role,
        "interview_type": interview.interview_type,
        "scheduled_at": interview.scheduled_at,
        "meeting_link": interview.meeting_link,
        "notes": interview.notes,
        "application_id": interview.application_id,
    }


# =========================================================
# CREATE INTERVIEW
# =========================================================

@app.post("/interviews")
def create_interview(
    data: InterviewRequest,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    if data.application_id:
        application = (
            db.query(Application)
            .filter(
                Application.id == data.application_id,
                Application.user_id == user.id,
            )
            .first()
        )

        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )

    interview = Interview(
        user_id=user.id,
        application_id=data.application_id,
        company=data.company.strip(),
        role=data.role.strip(),
        interview_type=data.interview_type,
        scheduled_at=data.scheduled_at,
        meeting_link=data.meeting_link,
        notes=data.notes,
    )

    db.add(interview)
    db.commit()
    db.refresh(interview)

    return interview_to_dict(
        interview
    )


# =========================================================
# GET INTERVIEWS
# =========================================================

@app.get("/interviews")
def get_interviews(
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    interviews = (
        db.query(Interview)
        .filter(
            Interview.user_id == user.id
        )
        .order_by(
            Interview.scheduled_at.asc()
        )
        .all()
    )

    return [
        interview_to_dict(item)
        for item in interviews
    ]


# =========================================================
# DELETE INTERVIEW
# =========================================================

@app.delete("/interviews/{interview_id}")
def delete_interview(
    interview_id: int,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(
            Interview.id == interview_id,
            Interview.user_id == user.id,
        )
        .first()
    )

    if not interview:
        raise HTTPException(
            status_code=404,
            detail="Interview not found.",
        )

    db.delete(interview)
    db.commit()

    return {
        "message": "Interview deleted successfully."
    }


# =========================================================
# RESUME UPLOAD
# =========================================================

@app.post("/resumes")
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Please select a file.",
        )

    allowed_extensions = {
        ".pdf",
        ".doc",
        ".docx",
    }

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOC and DOCX files are allowed.",
        )

    content = await file.read()

    max_size = 10 * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Resume must be smaller than 10 MB.",
        )

    stored_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    file_path = (
        UPLOAD_DIR / stored_filename
    )

    with open(
        file_path,
        "wb",
    ) as output:
        output.write(content)

    resume = Resume(
        user_id=user.id,
        filename=file.filename,
        stored_filename=stored_filename,
    )

    db.add(resume)
    db.commit()
    db.refresh(resume)

    return {
        "id": resume.id,
        "filename": resume.filename,
        "created_at": resume.created_at,
    }


# =========================================================
# GET RESUMES
# =========================================================

@app.get("/resumes")
def get_resumes(
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    resumes = (
        db.query(Resume)
        .filter(
            Resume.user_id == user.id
        )
        .order_by(
            Resume.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": resume.id,
            "filename": resume.filename,
            "created_at": resume.created_at,
        }
        for resume in resumes
    ]


# =========================================================
# DOWNLOAD RESUME
# =========================================================

@app.get("/resumes/{resume_id}/download")
def download_resume(
    resume_id: int,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id,
        )
        .first()
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )

    file_path = (
        UPLOAD_DIR
        / resume.stored_filename
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Resume file is missing.",
        )

    return FileResponse(
        path=file_path,
        filename=resume.filename,
    )


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics")
def analytics(
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    applications = (
        db.query(Application)
        .filter(
            Application.user_id == user.id
        )
        .all()
    )

    interviews = (
        db.query(Interview)
        .filter(
            Interview.user_id == user.id
        )
        .all()
    )

    total = len(applications)

    status_counts = {}

    for application in applications:
        status_counts[
            application.status
        ] = (
            status_counts.get(
                application.status,
                0,
            )
            + 1
        )

    selected = status_counts.get(
        "Selected",
        0,
    )

    rejected = status_counts.get(
        "Rejected",
        0,
    )

    interview_count = len(interviews)

    offer_rate = (
        round(
            selected / total * 100,
            2,
        )
        if total
        else 0
    )

    rejection_rate = (
        round(
            rejected / total * 100,
            2,
        )
        if total
        else 0
    )

    return {
        "total_applications": total,
        "total_interviews": interview_count,
        "selected": selected,
        "rejected": rejected,
        "offer_rate": offer_rate,
        "rejection_rate": rejection_rate,
        "status_breakdown": status_counts,
    }


# =========================================================
# GOOGLE CALENDAR
# =========================================================

@app.get(
    "/google-calendar-url/{interview_id}"
)
def google_calendar_url(
    interview_id: int,
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(
            Interview.id == interview_id,
            Interview.user_id == user.id,
        )
        .first()
    )

    if not interview:
        raise HTTPException(
            status_code=404,
            detail="Interview not found.",
        )

    start = interview.scheduled_at

    end = start + timedelta(
        hours=1
    )

    start_string = start.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    end_string = end.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    params = {
        "action": "TEMPLATE",
        "text": (
            f"{interview.company} - "
            f"{interview.role}"
        ),
        "dates": (
            f"{start_string}/{end_string}"
        ),
        "details": (
            interview.notes or ""
        ),
    }

    calendar_url = (
        "https://calendar.google.com/calendar/render?"
        + urlencode(params)
    )

    return {
        "url": calendar_url
    }


# =========================================================
# SMART INSIGHTS
# =========================================================

@app.get("/insights")
def insights(
    user: User = Depends(
        get_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    applications = (
        db.query(Application)
        .filter(
            Application.user_id == user.id
        )
        .all()
    )

    if not applications:
        return {
            "insights": [
                "Start adding applications to receive personalized insights."
            ]
        }

    total = len(applications)

    interviews = sum(
        1
        for application in applications
        if application.status == "Interview"
    )

    selected = sum(
        1
        for application in applications
        if application.status == "Selected"
    )

    rejected = sum(
        1
        for application in applications
        if application.status == "Rejected"
    )

    followups = sum(
        1
        for application in applications
        if application.follow_up_date
    )

    insights_list = []

    insights_list.append(
        f"You have tracked {total} application(s)."
    )

    if interviews:
        insights_list.append(
            f"{interviews} application(s) have reached the interview stage."
        )

    if selected:
        insights_list.append(
            f"You currently have {selected} selected application(s)."
        )

    if rejected:
        insights_list.append(
            f"{rejected} application(s) are marked as rejected."
        )

    if followups:
        insights_list.append(
            f"{followups} application(s) have follow-up dates."
        )

    if total >= 5 and interviews == 0:
        insights_list.append(
            "Consider reviewing your resume and application targeting because none of the tracked applications have reached the interview stage yet."
        )

    if total >= 5 and interviews > 0:
        interview_rate = round(
            interviews / total * 100,
            2,
        )

        insights_list.append(
            f"Your current application-to-interview rate is {interview_rate}%."
        )

    return {
        "insights": insights_list
    }
