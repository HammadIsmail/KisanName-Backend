"""
Migration: Drop old query_log table, create chat_sessions + new query_log.
Run once: python migrate.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Dropping old query_log...")
    conn.execute(text("DROP TABLE IF EXISTS query_log CASCADE;"))
    print("Dropping old chat_sessions if exists...")
    conn.execute(text("DROP TABLE IF EXISTS chat_sessions CASCADE;"))
    conn.commit()

# Now create all tables fresh
from models import user, crop, crop_area, chat_session, query_log  # noqa
from database import Base
Base.metadata.create_all(bind=engine)
print("✓ New tables created: chat_sessions, query_log")
