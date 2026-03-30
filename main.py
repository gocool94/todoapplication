from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import datetime
import os

app = FastAPI(title="Todo API", description="A simple CRUD todo list", version="1.0")

# -------------------- Database setup --------------------
DB_FILE = "todos.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# Initialize DB on startup
@app.on_event("startup")
def startup():
    init_db()

# -------------------- Pydantic models --------------------
class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True

# -------------------- API endpoints --------------------
@app.post("/todos", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO todos (title, description) VALUES (?, ?)",
            (todo.title, todo.description)
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (new_id,)).fetchone()
    return dict(row)

@app.get("/todos", response_model=List[TodoResponse])
def list_todos(completed: Optional[bool] = None):
    with get_db() as conn:
        if completed is None:
            rows = conn.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM todos WHERE completed = ? ORDER BY created_at DESC",
                (1 if completed else 0,)
            ).fetchall()
    return [dict(row) for row in rows]

@app.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Todo not found")
    return dict(row)

@app.put("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, update: TodoUpdate):
    with get_db() as conn:
        # First check if todo exists
        existing = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Todo not found")

        # Build dynamic update query
        fields = []
        values = []
        if update.title is not None:
            fields.append("title = ?")
            values.append(update.title)
        if update.description is not None:
            fields.append("description = ?")
            values.append(update.description)
        if update.completed is not None:
            fields.append("completed = ?")
            values.append(1 if update.completed else 0)

        if fields:
            query = f"UPDATE todos SET {', '.join(fields)} WHERE id = ?"
            values.append(todo_id)
            conn.execute(query, values)
            conn.commit()

        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return dict(row)

@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int):
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Todo not found")
    return None