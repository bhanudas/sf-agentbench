"""SQLite-based storage for Q&A test results.

Provides persistent storage, querying, and playback capabilities for Q&A runs.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class QAQuestionRecord:
    """Record of a single Q&A exchange for playback."""
    
    question_id: int | str
    domain: str
    difficulty: str
    question_text: str
    choices: dict[str, str]
    correct_answer: str
    prompt_sent: str
    model_response: str
    extracted_answer: str
    is_correct: bool
    response_time_seconds: float
    explanation: str = ""
    timestamp: str = ""


@dataclass 
class QARunRecord:
    """Complete record of a Q&A run."""
    
    run_id: str
    model_id: str
    cli_id: str
    test_bank_id: str
    test_bank_name: str
    started_at: datetime
    completed_at: datetime
    total_questions: int
    correct_answers: int
    accuracy: float
    duration_seconds: float
    questions: list[QAQuestionRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "model_id": self.model_id,
            "cli_id": self.cli_id,
            "test_bank_id": self.test_bank_id,
            "test_bank_name": self.test_bank_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "accuracy": self.accuracy,
            "duration_seconds": self.duration_seconds,
            "questions": [asdict(q) for q in self.questions],
            "metadata": self.metadata,
        }


class QAResultsStore:
    """Persistent storage for Q&A test results."""
    
    def __init__(self, results_dir: Path | str):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.results_dir / "qa_results.db"
        self.runs_dir = self.results_dir / "qa_runs"
        self.runs_dir.mkdir(exist_ok=True)
        
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Main runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_runs (
                    run_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    cli_id TEXT NOT NULL,
                    test_bank_id TEXT NOT NULL,
                    test_bank_name TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    total_questions INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    error TEXT,
                    run_file_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Per-question results for detailed analysis
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    domain TEXT,
                    difficulty TEXT,
                    question_text TEXT,
                    correct_answer TEXT,
                    model_response TEXT,
                    extracted_answer TEXT,
                    is_correct INTEGER,
                    response_time REAL,
                    timestamp TEXT,
                    FOREIGN KEY (run_id) REFERENCES qa_runs(run_id)
                )
            """)
            
            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_runs_model ON qa_runs(model_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_runs_bank ON qa_runs(test_bank_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_questions_run ON qa_questions(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_questions_domain ON qa_questions(domain)")
            
            conn.commit()
    
    def start_run(
        self,
        model_id: str,
        cli_id: str,
        test_bank_id: str,
        test_bank_name: str = "",
    ) -> str:
        """Start a new Q&A run and return the run_id."""
        run_id = str(uuid.uuid4())[:12]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO qa_runs (
                    run_id, model_id, cli_id, test_bank_id, test_bank_name,
                    started_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'running')
            """, (
                run_id, model_id, cli_id, test_bank_id, test_bank_name,
                datetime.now().isoformat()
            ))
            conn.commit()
        
        return run_id
    
    def log_question(
        self,
        run_id: str,
        question_id: int | str,
        domain: str,
        difficulty: str,
        question_text: str,
        correct_answer: str,
        prompt_sent: str,
        model_response: str,
        extracted_answer: str,
        is_correct: bool,
        response_time: float,
    ) -> None:
        """Log a single Q&A exchange."""
        timestamp = datetime.now().isoformat()
        
        # Store in database for querying
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO qa_questions (
                    run_id, question_id, domain, difficulty, question_text,
                    correct_answer, model_response, extracted_answer,
                    is_correct, response_time, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, str(question_id), domain, difficulty, question_text,
                correct_answer, model_response, extracted_answer,
                1 if is_correct else 0, response_time, timestamp
            ))
            conn.commit()
        
        # Also append to detailed log file for playback
        run_log = self.runs_dir / run_id / "questions.jsonl"
        run_log.parent.mkdir(parents=True, exist_ok=True)
        
        with open(run_log, "a") as f:
            record = {
                "question_id": question_id,
                "domain": domain,
                "difficulty": difficulty,
                "question_text": question_text,
                "correct_answer": correct_answer,
                "prompt_sent": prompt_sent,
                "model_response": model_response,
                "extracted_answer": extracted_answer,
                "is_correct": is_correct,
                "response_time": response_time,
                "timestamp": timestamp,
            }
            f.write(json.dumps(record) + "\n")
    
    def complete_run(
        self,
        run_id: str,
        total_questions: int,
        correct_answers: int,
        duration_seconds: float,
        error: str | None = None,
    ) -> None:
        """Mark a run as completed and save summary."""
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        status = "completed" if error is None else "failed"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE qa_runs SET
                    completed_at = ?,
                    total_questions = ?,
                    correct_answers = ?,
                    accuracy = ?,
                    duration_seconds = ?,
                    status = ?,
                    error = ?
                WHERE run_id = ?
            """, (
                datetime.now().isoformat(),
                total_questions,
                correct_answers,
                accuracy,
                duration_seconds,
                status,
                error,
                run_id
            ))
            conn.commit()
        
        # Save summary file
        summary_file = self.runs_dir / run_id / "summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        
        summary = self.get_run(run_id)
        if summary:
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2)
    
    def get_run(self, run_id: str) -> dict | None:
        """Get a run's summary data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM qa_runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return dict(row)
        return None
    
    def get_run_questions(self, run_id: str) -> list[dict]:
        """Get all question records for a run (for playback)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM qa_questions WHERE run_id = ? ORDER BY timestamp",
                (run_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def list_runs(
        self,
        model_id: str | None = None,
        test_bank_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List Q&A runs with optional filtering."""
        query = "SELECT * FROM qa_runs WHERE 1=1"
        params = []
        
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        
        if test_bank_id:
            query += " AND test_bank_id = ?"
            params.append(test_bank_id)
        
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_model_comparison(self, test_bank_id: str | None = None) -> list[dict]:
        """Compare models across runs."""
        query = """
            SELECT 
                model_id,
                COUNT(*) as run_count,
                AVG(accuracy) as avg_accuracy,
                MAX(accuracy) as best_accuracy,
                AVG(duration_seconds) as avg_duration,
                SUM(total_questions) as total_questions,
                SUM(correct_answers) as total_correct
            FROM qa_runs
            WHERE status = 'completed'
        """
        params = []
        
        if test_bank_id:
            query += " AND test_bank_id = ?"
            params.append(test_bank_id)
        
        query += " GROUP BY model_id ORDER BY avg_accuracy DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_domain_analysis(
        self,
        model_id: str | None = None,
        test_bank_id: str | None = None,
    ) -> list[dict]:
        """Analyze performance by domain."""
        query = """
            SELECT 
                q.domain,
                r.model_id,
                COUNT(*) as total_questions,
                SUM(q.is_correct) as correct_answers,
                ROUND(AVG(q.is_correct) * 100, 1) as accuracy,
                ROUND(AVG(q.response_time), 2) as avg_response_time
            FROM qa_questions q
            JOIN qa_runs r ON q.run_id = r.run_id
            WHERE r.status = 'completed'
        """
        params = []
        
        if model_id:
            query += " AND r.model_id = ?"
            params.append(model_id)
        
        if test_bank_id:
            query += " AND r.test_bank_id = ?"
            params.append(test_bank_id)
        
        query += " GROUP BY q.domain, r.model_id ORDER BY q.domain, accuracy DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_hardest_questions(self, limit: int = 10) -> list[dict]:
        """Find questions that models get wrong most often."""
        query = """
            SELECT 
                question_id,
                domain,
                question_text,
                correct_answer,
                COUNT(*) as times_asked,
                SUM(is_correct) as times_correct,
                ROUND(AVG(is_correct) * 100, 1) as accuracy
            FROM qa_questions
            GROUP BY question_id
            HAVING COUNT(*) >= 2
            ORDER BY accuracy ASC, times_asked DESC
            LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def playback_run(self, run_id: str) -> None:
        """Replay a Q&A run showing prompts and responses."""
        run = self.get_run(run_id)
        if not run:
            console.print(f"[red]Run not found: {run_id}[/red]")
            return
        
        questions = self.get_run_questions(run_id)
        
        console.print(f"\n[bold cyan]Q&A Run Playback: {run_id}[/bold cyan]")
        console.print(f"Model: [magenta]{run['model_id']}[/magenta]")
        console.print(f"Test Bank: {run['test_bank_id']}")
        console.print(f"Score: {run['correct_answers']}/{run['total_questions']} ({run['accuracy']:.1f}%)")
        console.print("=" * 60)
        
        for i, q in enumerate(questions, 1):
            status = "[green]✓[/green]" if q["is_correct"] else "[red]✗[/red]"
            
            console.print(f"\n{status} [bold]Question {i} (ID: {q['question_id']})[/bold]")
            console.print(f"[dim]Domain: {q['domain']} | Time: {q['response_time']:.1f}s[/dim]")
            console.print(f"\n[cyan]Q:[/cyan] {q['question_text']}")
            console.print(f"\n[yellow]Model Response:[/yellow]")
            console.print(f"  {q['model_response'][:200]}{'...' if len(q['model_response']) > 200 else ''}")
            console.print(f"\n[green]Expected:[/green] {q['correct_answer']} | [blue]Extracted:[/blue] {q['extracted_answer']}")
            console.print("-" * 60)
    
    def export_for_analysis(self, output_path: Path | str) -> None:
        """Export all data as CSV for external analysis."""
        import csv
        
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export runs
        runs = self.list_runs(limit=10000)
        with open(output_path / "qa_runs.csv", "w", newline="") as f:
            if runs:
                writer = csv.DictWriter(f, fieldnames=runs[0].keys())
                writer.writeheader()
                writer.writerows(runs)
        
        # Export questions
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM qa_questions")
            questions = [dict(row) for row in cursor.fetchall()]
        
        with open(output_path / "qa_questions.csv", "w", newline="") as f:
            if questions:
                writer = csv.DictWriter(f, fieldnames=questions[0].keys())
                writer.writeheader()
                writer.writerows(questions)
        
        console.print(f"[green]Exported to {output_path}[/green]")
