from fastapi import FastAPI

app = FastAPI(
    title="Job Application Tracker API",
    description="Backend API for managing job and internship applications.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Job Application Tracker API is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
