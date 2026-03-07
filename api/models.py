"""Pydantic request/response schemas for the Paper Boy API."""

from typing import Dict, List, Optional

from pydantic import BaseModel


# ── Build ──


class FeedInput(BaseModel):
    name: str
    url: str


class BuildRequest(BaseModel):
    title: str = "Morning Digest"
    language: str = "en"
    max_articles_per_feed: int = 10
    include_images: bool = True
    feeds: List[FeedInput]
    device: str = "kobo"
    edition_date: Optional[str] = None


class BuildResponse(BaseModel):
    success: bool
    epub_base64: Optional[str] = None
    total_articles: int = 0
    sections: List[dict] = []
    file_size: str = "0 KB"
    file_size_bytes: int = 0
    error: Optional[str] = None


# ── Deliver ──


class DeliverRequest(BaseModel):
    epub_base64: str
    title: str = "Morning Digest"
    device: str = "kobo"
    delivery_method: str = "local"
    google_drive_folder: str = "Rakuten Kobo"
    google_tokens: Optional[Dict] = None
    kindle_email: str = ""
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 465
    email_sender: str = ""
    email_password: str = ""


class DeliverResponse(BaseModel):
    success: bool
    message: str


# ── SMTP Test ──


class SmtpTestRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    sender: str
    password: str


class SmtpTestResponse(BaseModel):
    success: bool
    message: str


# ── Feed Validation ──


class FeedValidateRequest(BaseModel):
    url: str


class FeedValidateResponse(BaseModel):
    valid: bool
    name: Optional[str] = None
    error: Optional[str] = None
