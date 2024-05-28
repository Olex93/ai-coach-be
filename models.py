from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class EmailVerificationInput(BaseModel):
    email: EmailStr
    code: str


class UserDetailsUpdate(BaseModel):
    height: int
    weight: int
    age: int
    gender: str
    goals: str


class UserWorkoutNotesInput(BaseModel):
    notes: str
