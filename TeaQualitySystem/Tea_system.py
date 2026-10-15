"""
TEA RECEPTION QUALITY TRACKING SYSTEM - SINGLE FILE VERSION
Version 3.0
A complete offline desktop application for tea factories

CHANGES IN THIS VERSION:
- Added Tab key support for saving batches (Ctrl+S or Tab from last field)
- Added weight-based quality calculation method as alternative to leaf counting
- Enhanced reporting with filtering by center, truck, and date range
- Improved admin visibility with dedicated admin dashboard
- Full CRUD operations for centers, trucks, drivers, and users
- Enhanced role-based access control
"""

import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog
import sqlite3
import hashlib
import os
import sys
import shutil
from datetime import datetime, timedelta

# ==================== SETTINGS ====================
APP_NAME = "Tea Reception Quality Tracking System"
APP_VERSION = "3.0"
DB_FILE = 'Tea_factory.db'
BACKUP_DIR = 'backups'
REPORTS_DIR = 'reports'

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

GOOD_CATEGORIES = [
    ("leaf_1bud", "1 Leaf + Bud"),
    ("leaf_2bud", "2 Leaves + Bud"),
    ("soft_bhanji", "Soft Bhanji"),
]
BAD_CATEGORIES = [
    ("leaf_3bud", "3 Leaves + Bud"),
    ("hard_leaf", "Hard Leaf"),
    ("loose_leaves", "Loose Leaves"),
    ("stalky_bruised", "Stalky & Bruised"),
    ("stems_stalks", "Stems & Stalks"),
]
ALL_CATEGORIES = GOOD_CATEGORIES + BAD_CATEGORIES


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ==================== THEME / DESIGN SYSTEM ====================
class Theme:
    # core palette - deep tea green primary, warm neutral background
    PRIMARY = "#1b4332"
    PRIMARY_DARK = "#0d2b20"
    PRIMARY_LIGHT = "#2d6a4f"
    ACCENT = "#40916c"
    ACCENT_LIGHT = "#95d5b2"

    BG = "#f4f6f5"
    CARD = "#ffffff"
    BORDER = "#dde3e0"
    HEADER_TEXT = "#ffffff"

    TEXT = "#1f2a24"
    TEXT_MUTED = "#647268"
    TEXT_ON_PRIMARY = "#ffffff"

    SUCCESS = "#2f9e44"
    SUCCESS_BG = "#e6f7ec"
    INFO = "#1d68c9"
    INFO_BG = "#e8f1fc"
    WARNING = "#b8860b"
    WARNING_BG = "#fdf3d9"
    DANGER = "#c0392b"
    DANGER_BG = "#fbe9e7"

    FONT_FAMILY = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"

    @classmethod
    def f(cls, size=12, weight="normal"):
        return (cls.FONT_FAMILY, size, weight)


def quality_tier(quality):
    if quality >= 70:
        return "EXCELLENT", Theme.SUCCESS, Theme.SUCCESS_BG, "\u2714"
    elif quality >= 60:
        return "GOOD", Theme.INFO, Theme.INFO_BG, "\u25cf"
    elif quality >= 50:
        return "AVERAGE", Theme.WARNING, Theme.WARNING_BG, "\u26a0"
    else:
        return "CRITICAL", Theme.DANGER, Theme.DANGER_BG, "\u2716"


def configure_styles(root):
    """Configure ttk widget styles for a consistent, modern look."""
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    style.configure('TCombobox',
                     fieldbackground=Theme.CARD,
                     background=Theme.CARD,
                     bordercolor=Theme.BORDER,
                     arrowcolor=Theme.PRIMARY,
                     padding=6)
    style.map('TCombobox', fieldbackground=[('readonly', Theme.CARD)])

    style.configure('Treeview',
                     background=Theme.CARD,
                     fieldbackground=Theme.CARD,
                     foreground=Theme.TEXT,
                     rowheight=26,
                     font=Theme.f(9),
                     borderwidth=0)
    style.configure('Treeview.Heading',
                     background=Theme.PRIMARY,
                     foreground=Theme.TEXT_ON_PRIMARY,
                     font=Theme.f(9, 'bold'),
                     relief='flat')
    style.map('Treeview.Heading', background=[('active', Theme.PRIMARY_DARK)])
    style.map('Treeview', background=[('selected', Theme.ACCENT_LIGHT)],
              foreground=[('selected', Theme.TEXT)])

    style.configure('TSeparator', background=Theme.BORDER)

    style.configure('Vertical.TScrollbar', background=Theme.BORDER, troughcolor=Theme.BG, arrowcolor=Theme.TEXT_MUTED)
    style.configure('Horizontal.TScrollbar', background=Theme.BORDER, troughcolor=Theme.BG, arrowcolor=Theme.TEXT_MUTED)


def make_button(parent, text, command, kind="primary", width=None, pady=8, padx=16):
    """Consistent button factory with hover effect. kind: primary|success|danger|neutral|outline"""
    palette = {
        "primary": (Theme.PRIMARY, "#22543d", Theme.TEXT_ON_PRIMARY),
        "success": (Theme.ACCENT, Theme.PRIMARY_LIGHT, Theme.TEXT_ON_PRIMARY),
        "danger": (Theme.DANGER, "#96281b", Theme.TEXT_ON_PRIMARY),
        "neutral": ("#8a9a91", "#6f8177", Theme.TEXT_ON_PRIMARY),
        "outline": (Theme.CARD, Theme.BG, Theme.PRIMARY),
    }
    bg, hover_bg, fg = palette.get(kind, palette["primary"])
    btn = tk.Button(
        parent, text=text, command=command, bg=bg, fg=fg,
        activebackground=hover_bg, activeforeground=fg,
        font=Theme.f(10, 'bold'), relief='flat', bd=0, cursor='hand2',
        padx=padx, pady=pady, highlightthickness=1, highlightbackground=Theme.BORDER
    )
    if width:
        btn.config(width=width)
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def card_frame(parent, **kwargs):
    """A white 'card' panel with a subtle border, used throughout the UI."""
    outer = tk.Frame(parent, bg=Theme.BORDER)
    inner = tk.Frame(outer, bg=Theme.CARD, **kwargs)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    return outer, inner


def section_label(parent, text, icon=""):
    lbl = tk.Label(parent, text=f"{icon}  {text}".strip(), font=Theme.f(11, 'bold'),
                    bg=Theme.CARD, fg=Theme.PRIMARY, anchor='w')
    return lbl


def badge(parent, text, fg, bg, font_size=10):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=Theme.f(font_size, 'bold'),
                     padx=10, pady=4)


# ==================== DATABASE MANAGER ====================
class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.connect()
        self.init_tables()
        self.insert_sample_data()

    def connect(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def init_tables(self):
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buying_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                code TEXT UNIQUE NOT NULL,
                location TEXT,
                contact_person TEXT,
                phone TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trucks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration TEXT UNIQUE NOT NULL,
                driver_name TEXT NOT NULL,
                driver_phone TEXT,
                owner_name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                date TEXT NOT NULL,
                buying_center TEXT NOT NULL,
                truck_registration TEXT NOT NULL,
                driver_name TEXT NOT NULL,
                total_kg REAL NOT NULL,
                leaf_1bud INTEGER NOT NULL DEFAULT 0,
                leaf_2bud INTEGER NOT NULL DEFAULT 0,
                soft_bhanji INTEGER NOT NULL DEFAULT 0,
                leaf_3bud INTEGER NOT NULL DEFAULT 0,
                hard_leaf INTEGER NOT NULL DEFAULT 0,
                loose_leaves INTEGER NOT NULL DEFAULT 0,
                stalky_bruised INTEGER NOT NULL DEFAULT 0,
                stems_stalks INTEGER NOT NULL DEFAULT 0,
                total_good INTEGER NOT NULL,
                total_bad INTEGER NOT NULL,
                total_leaves INTEGER NOT NULL,
                quality_percent REAL NOT NULL,
                quality_method TEXT DEFAULT 'leaf_count',
                timestamp TEXT NOT NULL,
                entered_by TEXT DEFAULT 'operator'
            )
        ''')

        self.conn.commit()

    def insert_sample_data(self):
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM buying_centers")
        if cursor.fetchone()[0] == 0:
            sample_centers = [
                ("Kaimosi Farm", "KAI", "Kaimosi", "John Kipchoge", "0712345678"),
                ("Chebichi Center", "CHE", "Chebichi", "Mary Wanjiku", "0723456789"),
                ("Serem Depot", "SER", "Serem", "Peter Okoth", "0734567890"),
                ("Lwandeti Hub", "LWA", "Lwandeti", "James Otieno", "0745678901"),
                ("Kapsokwony Center", "KAP", "Kapsokwony", "Sarah Chemutai", "0756789012")
            ]
            cursor.executemany(
                "INSERT INTO buying_centers (name, code, location, contact_person, phone) VALUES (?,?,?,?,?)",
                sample_centers
            )

        cursor.execute("SELECT COUNT(*) FROM trucks")
        if cursor.fetchone()[0] == 0:
            sample_trucks = [
                ("KCD 123J", "John Mwangi", "0712345678", "Mwangi Transport"),
                ("KBB 456M", "Peter Okoth", "0723456789", "Okoth Logistics"),
                ("KCM 789P", "James Otieno", "0734567890", "Otieno Hauliers"),
                ("KAX 012L", "Samuel Kipchoge", "0745678901", "Kipchoge Enterprises"),
                ("KBA 567M", "Richard Kori", "0756789012", "Kori Traders")
            ]
            cursor.executemany(
                "INSERT INTO trucks (registration, driver_name, driver_phone, owner_name) VALUES (?,?,?,?)",
                sample_trucks
            )

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ('admin', hash_password('admin123'), 'admin')
            )
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ('operator', hash_password('operator123'), 'user')
            )

        self.conn.commit()

    # ---------- lookups ----------
    def get_center_names(self):
        return [row[0] for row in self.conn.execute("SELECT name FROM buying_centers ORDER BY name").fetchall()]

    def get_center_code(self, name):
        row = self.conn.execute("SELECT code FROM buying_centers WHERE name = ?", (name,)).fetchone()
        return row[0] if row else "GEN"

    def get_truck_registrations(self):
        return [row[0] for row in self.conn.execute("SELECT registration FROM trucks ORDER BY registration").fetchall()]

    def get_driver_by_truck(self, registration):
        result = self.conn.execute(
            "SELECT driver_name FROM trucks WHERE registration = ?",
            (registration,)
        ).fetchone()
        return result[0] if result else None

    # ---------- batch id generation ----------
    def generate_batch_id(self, center_name, date_str):
        code = self.get_center_code(center_name)
        date_compact = date_str.replace('-', '')[2:]
        count = self.conn.execute(
            "SELECT COUNT(*) FROM batches WHERE buying_center = ? AND date = ?",
            (center_name, date_str)
        ).fetchone()[0]
        seq = count + 1
        candidate = f"{code}-{date_compact}-{seq:03d}"
        while self.conn.execute("SELECT 1 FROM batches WHERE batch_id = ?", (candidate,)).fetchone():
            seq += 1
            candidate = f"{code}-{date_compact}-{seq:03d}"
        return candidate

    # ---------- batches ----------
    def save_batch(self, data):
        cursor = self.conn.cursor()
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        query = f"INSERT INTO batches ({columns}) VALUES ({placeholders})"
        cursor.execute(query, list(data.values()))
        self.conn.commit()
        return cursor.lastrowid

    def get_batches_between(self, start_date, end_date, center=None, truck=None):
        query = '''
            SELECT * FROM batches
            WHERE date BETWEEN ? AND ?
        '''
        params = [start_date, end_date]
        
        if center:
            query += " AND buying_center = ?"
            params.append(center)
        if truck:
            query += " AND truck_registration = ?"
            params.append(truck)
            
        query += " ORDER BY date, id"
        return self.conn.execute(query, params).fetchall()

    def get_batches_on(self, date):
        return self.get_batches_between(date, date)

    def get_recent_batches(self, limit=10):
        return self.conn.execute('''
            SELECT batch_id, buying_center, truck_registration, total_kg,
                   quality_percent, SUBSTR(timestamp, 12, 5), quality_method
            FROM batches
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,)).fetchall()

    def get_all_batches(self):
        return self.conn.execute('''
            SELECT id, batch_id, date, buying_center, truck_registration, driver_name,
                   total_kg, total_good, total_bad, total_leaves, quality_percent, 
                   quality_method, entered_by
            FROM batches ORDER BY id DESC
        ''').fetchall()

    # ---------- users ----------
    def get_user(self, username, password):
        row = self.conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return None
        if row['password'] == hash_password(password):
            return row
        if row['password'] == password:
            self.conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hash_password(password), row['id'])
            )
            self.conn.commit()
            return row
        return None

    def get_all_users(self):
        return self.conn.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()

    def add_user(self, username, password, role):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?,?,?)",
            (username, hash_password(password), role)
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_user(self, user_id):
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    def count_admins(self):
        return self.conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]

    # ---------- admin: buying centers ----------
    def add_buying_center(self, name, location, contact_person, phone):
        base_code = ''.join(ch for ch in name.upper() if ch.isalpha())[:3] or "CTR"
        code = base_code
        n = 1
        existing_codes = {r[0] for r in self.conn.execute("SELECT code FROM buying_centers").fetchall()}
        while code in existing_codes:
            n += 1
            code = f"{base_code[:2]}{n}"
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO buying_centers (name, code, location, contact_person, phone) VALUES (?,?,?,?,?)",
            (name, code, location, contact_person, phone)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_buying_center(self, center_id, name, location, contact_person, phone):
        self.conn.execute(
            "UPDATE buying_centers SET name=?, location=?, contact_person=?, phone=? WHERE id=?",
            (name, location, contact_person, phone, center_id)
        )
        self.conn.commit()

    def delete_buying_center(self, center_id):
        self.conn.execute("DELETE FROM buying_centers WHERE id = ?", (center_id,))
        self.conn.commit()

    def get_all_centers_full(self):
        return self.conn.execute("SELECT * FROM buying_centers ORDER BY name").fetchall()

    # ---------- admin: trucks ----------
    def add_truck(self, registration, driver_name, driver_phone, owner_name):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO trucks (registration, driver_name, driver_phone, owner_name) VALUES (?,?,?,?)",
            (registration, driver_name, driver_phone, owner_name)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_truck(self, truck_id, registration, driver_name, driver_phone, owner_name):
        self.conn.execute(
            "UPDATE trucks SET registration=?, driver_name=?, driver_phone=?, owner_name=? WHERE id=?",
            (registration, driver_name, driver_phone, owner_name, truck_id)
        )
        self.conn.commit()

    def delete_truck(self, truck_id):
        self.conn.execute("DELETE FROM trucks WHERE id = ?", (truck_id,))
        self.conn.commit()

    def get_all_trucks_full(self):
        return self.conn.execute("SELECT * FROM trucks ORDER BY registration").fetchall()

    # ---------- today stats ----------
    def get_today_stats(self, date):
        result = self.conn.execute('''
            SELECT COUNT(*), COALESCE(AVG(quality_percent), 0), COALESCE(SUM(total_kg), 0)
            FROM batches WHERE date = ?
        ''', (date,)).fetchone()
        return {'count': result[0], 'avg_quality': result[1], 'total_kg': result[2]}

    def get_best_worst(self, date, group_col):
        best = self.conn.execute(f'''
            SELECT {group_col}, AVG(quality_percent) as avg_q FROM batches
            WHERE date = ? GROUP BY {group_col} ORDER BY avg_q DESC LIMIT 1
        ''', (date,)).fetchone()
        worst = self.conn.execute(f'''
            SELECT {group_col}, AVG(quality_percent) as avg_q FROM batches
            WHERE date = ? GROUP BY {group_col} ORDER BY avg_q ASC LIMIT 1
        ''', (date,)).fetchone()
        return best, worst


# ==================== REPORT BUILDING ====================
def build_aggregate_report(rows, title, period_label, center_filter=None, truck_filter=None):
    lines = []
    lines.append("=" * 78)
    lines.append(title)
    lines.append(period_label)
    if center_filter:
        lines.append(f"Filtered by Buying Center: {center_filter}")
    if truck_filter:
        lines.append(f"Filtered by Truck: {truck_filter}")
    lines.append("=" * 78)

    if not rows:
        lines.append("\nNo batches recorded for this period.\n")
        return "\n".join(lines)

    total_batches = len(rows)
    total_kg = sum(row['total_kg'] for row in rows)
    total_good = sum(row['total_good'] for row in rows)
    total_bad = sum(row['total_bad'] for row in rows)
    total_leaves = sum(row['total_leaves'] for row in rows)
    avg_quality = sum(row['quality_percent'] for row in rows) / total_batches if total_batches > 0 else 0
    factory_quality = (total_good / total_leaves * 100) if total_leaves else 0

    lines.append("\nFACTORY-WIDE SUMMARY")
    lines.append("-" * 78)
    lines.append(f"Total Batches (samples):      {total_batches}")
    lines.append(f"Total Tea Received:           {total_kg:,.1f} kg")
    lines.append(f"Total Leaves Sampled:         {total_leaves}")
    lines.append(f"Total Good Leaves:            {total_good}")
    lines.append(f"Total Bad Leaves:             {total_bad}")
    lines.append(f"Average Quality (per-batch):  {avg_quality:.1f}%")
    lines.append(f"Overall Quality (pooled):     {factory_quality:.1f}%")

    lines.append("\n" + "-" * 78)
    lines.append("BY BUYING CENTER")
    lines.append("-" * 78)
    centers = {}
    for r in rows:
        center_name = r['buying_center']
        if center_name not in centers:
            centers[center_name] = {'n': 0, 'kg': 0, 'good': 0, 'leaves': 0, 'qsum': 0}
        c = centers[center_name]
        c['n'] += 1
        c['kg'] += r['total_kg']
        c['good'] += r['total_good']
        c['leaves'] += r['total_leaves']
        c['qsum'] += r['quality_percent']
    
    for name, c in sorted(centers.items(), key=lambda kv: -kv[1]['qsum'] / kv[1]['n'] if kv[1]['n'] > 0 else 0):
        avg_q = c['qsum'] / c['n'] if c['n'] > 0 else 0
        lines.append(f"{name:<25} samples: {c['n']:<4} kg: {c['kg']:>9,.1f}   avg quality: {avg_q:>5.1f}%")

    lines.append("\n" + "-" * 78)
    lines.append("BY TRUCK / DRIVER")
    lines.append("-" * 78)
    trucks = {}
    for r in rows:
        key = (r['truck_registration'], r['driver_name'])
        if key not in trucks:
            trucks[key] = {'n': 0, 'kg': 0, 'qsum': 0}
        t = trucks[key]
        t['n'] += 1
        t['kg'] += r['total_kg']
        t['qsum'] += r['quality_percent']
    
    for (reg, driver), t in sorted(trucks.items(), key=lambda kv: -kv[1]['qsum'] / kv[1]['n'] if kv[1]['n'] > 0 else 0):
        avg_q = t['qsum'] / t['n'] if t['n'] > 0 else 0
        label = f"{reg} ({driver})"
        lines.append(f"{label:<35} samples: {t['n']:<4} kg: {t['kg']:>9,.1f}   avg quality: {avg_q:>5.1f}%")

    days = {}
    for r in rows:
        date_str = r['date']
        if date_str not in days:
            days[date_str] = {'n': 0, 'qsum': 0, 'kg': 0}
        d = days[date_str]
        d['n'] += 1
        d['qsum'] += r['quality_percent']
        d['kg'] += r['total_kg']
    
    if len(days) > 1:
        lines.append("\n" + "-" * 78)
        lines.append("DAILY TREND")
        lines.append("-" * 78)
        for date_str in sorted(days.keys()):
            d = days[date_str]
            lines.append(f"{date_str}   batches: {d['n']:<4} kg: {d['kg']:>9,.1f}   avg quality: {d['qsum']/d['n']:>5.1f}%")

    lines.append("\n" + "-" * 78)
    lines.append("FULL SAMPLE DATA (every batch recorded this period)")
    lines.append("-" * 78)
    short_labels = ["1L+B", "2L+B", "SoftB", "3L+B", "Hard", "Loose", "Stalky", "Stems"]
    header = (f"{'Batch ID':<16}{'Date':<12}{'Center':<16}{'Truck':<11}{'Driver':<16}"
              f"{'kg':>8} " + " ".join(f"{lbl:>6}" for lbl in short_labels) +
              f" {'Good':>5}{'Bad':>5}{'Tot':>5}{'Qual%':>7} {'Method':>8}")
    lines.append(header)
    lines.append("-" * len(header))
    
    for r in rows:
        # Build category values using direct indexing (sqlite3.Row supports this)
        cat_values = []
        for key, _ in ALL_CATEGORIES:
            try:
                val = r[key]
            except (KeyError, IndexError):
                val = 0
            cat_values.append(f"{val:>6}")
        cat_vals = " ".join(cat_values)
        
        # Get method safely
        try:
            method = r['quality_method'] if r['quality_method'] else 'leaf_count'
        except (KeyError, IndexError):
            method = 'leaf_count'
        
        lines.append(
            f"{r['batch_id']:<16}{r['date']:<12}{r['buying_center']:<16}{r['truck_registration']:<11}"
            f"{r['driver_name']:<16}{r['total_kg']:>8,.1f} {cat_vals} "
            f"{r['total_good']:>5}{r['total_bad']:>5}{r['total_leaves']:>5}{r['quality_percent']:>7.1f} {method[:8]:>8}"
        )

    lines.append("\n" + "-" * 78)
    lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{APP_NAME} v{APP_VERSION}")
    lines.append("-" * 78)

    return "\n".join(lines)


# ==================== LOGIN WINDOW ====================
class LoginWindow:
    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.db = DatabaseManager()

        configure_styles(self.root)

        self.root.title("Login - Tea Quality System")
        self.root.geometry("980x620")
        self.root.configure(bg=Theme.PRIMARY_DARK)
        self.root.minsize(900, 580)

        self.create_login_form()

    def create_login_form(self):
        container = tk.Frame(self.root, bg=Theme.PRIMARY_DARK)
        container.pack(fill=tk.BOTH, expand=True)

        brand = tk.Frame(container, bg=Theme.PRIMARY_DARK, width=460)
        brand.pack(side=tk.LEFT, fill=tk.BOTH)
        brand.pack_propagate(False)

        tk.Label(brand, text="\U0001F343", font=("Segoe UI Emoji", 46), bg=Theme.PRIMARY_DARK,
                 fg=Theme.ACCENT_LIGHT).pack(pady=(120, 10))
        tk.Label(brand, text="TEA QUALITY", font=Theme.f(26, 'bold'), bg=Theme.PRIMARY_DARK,
                 fg="white").pack()
        tk.Label(brand, text="TRACKING SYSTEM", font=Theme.f(14, 'normal'), bg=Theme.PRIMARY_DARK,
                 fg=Theme.ACCENT_LIGHT).pack(pady=(0, 20))
        tk.Label(brand, text="Batch quality, by buying center,\ntruck and driver \u2014 tracked daily.",
                 font=Theme.f(10), bg=Theme.PRIMARY_DARK, fg="#a9c3b7", justify='center').pack()
        tk.Label(brand, text=f"v{APP_VERSION}", font=Theme.f(9), bg=Theme.PRIMARY_DARK,
                 fg="#6f8c7f").pack(side=tk.BOTTOM, pady=20)

        right = tk.Frame(container, bg=Theme.BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        card_outer, card = card_frame(right, padx=45, pady=40)
        card_outer.place(relx=0.5, rely=0.5, anchor='center', width=380, height=420)

        tk.Label(card, text="Welcome back", font=Theme.f(18, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w')
        tk.Label(card, text="Sign in to continue", font=Theme.f(10), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w', pady=(0, 25))

        tk.Label(card, text="USERNAME", font=Theme.f(8, 'bold'), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w')
        self.username_entry = tk.Entry(card, font=Theme.f(11), relief='flat', bg="#eef2f0",
                                        highlightthickness=1, highlightbackground=Theme.BORDER,
                                        highlightcolor=Theme.ACCENT, insertbackground=Theme.TEXT)
        self.username_entry.pack(fill=tk.X, ipady=8, pady=(5, 18))
        self.username_entry.focus()

        tk.Label(card, text="PASSWORD", font=Theme.f(8, 'bold'), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w')
        self.password_entry = tk.Entry(card, font=Theme.f(11), relief='flat', bg="#eef2f0", show='\u2022',
                                        highlightthickness=1, highlightbackground=Theme.BORDER,
                                        highlightcolor=Theme.ACCENT, insertbackground=Theme.TEXT)
        self.password_entry.pack(fill=tk.X, ipady=8, pady=(5, 28))

        login_btn = make_button(card, "SIGN IN", self.login, kind="primary")
        login_btn.pack(fill=tk.X, ipady=4)

        ttk.Separator(card, orient='horizontal').pack(fill=tk.X, pady=20)

        tk.Label(card, text="Default logins", font=Theme.f(8, 'bold'), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w')
        tk.Label(card, text="admin / admin123   \u00b7   operator / operator123",
                 font=Theme.f(9), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w', pady=(3, 0))

        self.root.bind('<Return>', lambda e: self.login())

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password")
            return

        user = self.db.get_user(username, password)
        if user:
            self.on_login_success(user)
        else:
            messagebox.showerror("Error", "Invalid username or password")


# ==================== MAIN APPLICATION ====================
class TeaQualitySystem:
    def __init__(self, root, user, on_logout):
        self.root = root
        self.user = user
        self.on_logout = on_logout
        self.is_admin = (user['role'] == 'admin')
        self.db = DatabaseManager()
        self.count_entries = {}

        configure_styles(self.root)

        self.root.title(f"{APP_NAME}")
        self.root.geometry("1360x900")
        self.root.configure(bg=Theme.BG)
        self.root.minsize(1150, 700)

        self.create_menu()
        self.create_header()
        self.create_main_layout()
        self.create_status_bar()
        self.load_data()
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_batch())
        self.root.bind('<Tab>', self.on_tab_pressed)

    # ---------------- menu ----------------
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Generate Report", command=self.show_report_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self.backup_database)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self.logout)
        file_menu.add_command(label="Exit", command=self.root.quit)

        data_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Data", menu=data_menu)
        data_menu.add_command(label="View All Batches", command=self.view_all_batches)
        data_menu.add_separator()
    
        if self.is_admin:
            admin_menu = tk.Menu(data_menu, tearoff=0)
            data_menu.add_cascade(label="Administrative Tasks", menu=admin_menu)
        
            admin_menu.add_command(label="\u270F  Manage Buying Centers", command=self.manage_buying_centers)
            admin_menu.add_command(label="\u270F  Manage Trucks & Drivers", command=self.manage_trucks)
            admin_menu.add_command(label="\u270F  Manage Users", command=self.manage_users)
            admin_menu.add_separator()
            admin_menu.add_command(label="\uD83D\uDCCA  Admin Dashboard", command=self.show_admin_dashboard)
        
            data_menu.add_separator()
            data_menu.add_command(label="\uD83D\uDCCA  Admin Dashboard", command=self.show_admin_dashboard)
        else:
            data_menu.add_command(label="Administrative Tasks (Admin Only)", state=tk.DISABLED)
            data_menu.add_command(label="Manage Buying Centers (Admin Only)", state=tk.DISABLED)
            data_menu.add_command(label="Manage Trucks (Admin Only)", state=tk.DISABLED)
            data_menu.add_command(label="Manage Users (Admin Only)", state=tk.DISABLED)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About", command=self.show_about)

    # ---------------- header ----------------
    def create_header(self):
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=64)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        left = tk.Frame(header, bg=Theme.PRIMARY)
        left.pack(side=tk.LEFT, padx=24)
        tk.Label(left, text="\U0001F343", font=("Segoe UI Emoji", 20), bg=Theme.PRIMARY, fg=Theme.ACCENT_LIGHT).pack(side=tk.LEFT, padx=(0, 10))
        title_box = tk.Frame(left, bg=Theme.PRIMARY)
        title_box.pack(side=tk.LEFT)
        tk.Label(title_box, text=APP_NAME, font=Theme.f(14, 'bold'), bg=Theme.PRIMARY, fg="white").pack(anchor='w')
        tk.Label(title_box, text=f"v{APP_VERSION}", font=Theme.f(8), bg=Theme.PRIMARY, fg=Theme.ACCENT_LIGHT).pack(anchor='w')

        right = tk.Frame(header, bg=Theme.PRIMARY)
        right.pack(side=tk.RIGHT, padx=24)

        role_bg = "#8e44ad" if self.is_admin else Theme.PRIMARY_LIGHT
        role_text = "ADMIN" if self.is_admin else "OPERATOR"
        badge(right, role_text, "white", role_bg, font_size=8).pack(side=tk.LEFT, padx=(0, 10), ipady=1)
        tk.Label(right, text=self.user['username'], font=Theme.f(11, 'bold'), bg=Theme.PRIMARY, fg="white").pack(side=tk.LEFT, padx=(0, 20))

        make_button(right, "Logout", self.logout, kind="outline", pady=5, padx=14).pack(side=tk.LEFT)

    # ---------------- status bar ----------------
    def create_status_bar(self):
        bar = tk.Frame(self.root, bg=Theme.PRIMARY_DARK, height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
    
        admin_indicator = " [ADMIN MODE]" if self.is_admin else ""
        self.status_var = tk.StringVar(
        value=f"Ready  \u00b7  Database: {DB_FILE}  \u00b7  {datetime.now().strftime('%A, %d %B %Y')}  \u00b7  Press Ctrl+S to save batch{admin_indicator}"
        )
        tk.Label(bar, textvariable=self.status_var, font=Theme.f(9), bg=Theme.PRIMARY_DARK, fg="#9db8ab").pack(side=tk.LEFT, padx=15)
    
        if self.is_admin:
            tk.Label(bar, text="ADMIN", font=Theme.f(9, 'bold'), bg=Theme.PRIMARY_DARK, fg="#ffd700").pack(side=tk.RIGHT, padx=15)

    # ---------------- layout ----------------
    def create_main_layout(self):
        main_container = tk.Frame(self.root, bg=Theme.BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        top_row = tk.Frame(main_container, bg=Theme.BG)
        top_row.pack(fill=tk.BOTH, expand=True)

        self.create_entry_form(top_row)
        self.create_stats_panel(top_row)

        self.create_recent_batches(main_container)

    def create_entry_form(self, parent):
        outer, form = card_frame(parent, padx=22, pady=20)
        outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        section_label(form, "BATCH DATA ENTRY", "\U0001F4CB").pack(anchor='w', pady=(0, 2))
        tk.Label(form, text="Counting-method quality sample \u2014 one per truck delivery",
                 font=Theme.f(9), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w', pady=(0, 15))

        grid = tk.Frame(form, bg=Theme.CARD)
        grid.pack(fill=tk.X)

        def field_label(text):
            return tk.Label(grid, text=text, font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT)

        row = 0
        field_label("Buying Center").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.center_combo = ttk.Combobox(grid, width=28, font=Theme.f(10), state='readonly')
        self.center_combo.grid(row=row, column=1, pady=6, padx=(10, 0), sticky=tk.W)
        self.center_combo.bind('<<ComboboxSelected>>', self.on_center_selected)
        row += 1

        field_label("Truck Registration").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.truck_combo = ttk.Combobox(grid, width=28, font=Theme.f(10), state='readonly')
        self.truck_combo.grid(row=row, column=1, pady=6, padx=(10, 0), sticky=tk.W)
        self.truck_combo.bind('<<ComboboxSelected>>', self.on_truck_selected)
        row += 1

        field_label("Driver Name").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.driver_entry = tk.Entry(grid, width=31, font=Theme.f(10), bg="#eef2f0", relief='flat',
                                      highlightthickness=1, highlightbackground=Theme.BORDER, state='readonly')
        self.driver_entry.grid(row=row, column=1, pady=6, padx=(10, 0), sticky=tk.W, ipady=3)
        row += 1

        field_label("Batch ID (auto-generated)").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.batch_id_label = badge(grid, "-- select a center --", Theme.INFO, Theme.INFO_BG, font_size=9)
        self.batch_id_label.grid(row=row, column=1, sticky=tk.W, pady=6, padx=(10, 0))
        row += 1

        field_label("Total Weight Delivered (kg)").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.total_kg_entry = tk.Entry(grid, width=14, font=Theme.f(10), relief='flat', bg="#eef2f0",
                                        highlightthickness=1, highlightbackground=Theme.BORDER)
        self.total_kg_entry.grid(row=row, column=1, pady=6, padx=(10, 0), sticky=tk.W, ipady=3)
        row += 1

        ttk.Separator(form, orient='horizontal').pack(fill=tk.X, pady=16)

        # ===== QUALITY SECTION - RESPONSIVE =====
        quality_section = tk.Frame(form, bg=Theme.CARD)
        quality_section.pack(fill=tk.BOTH, expand=True)
        
        # Quality method selection at top of section (ONLY ONE - DUPLICATE REMOVED)
        method_frame = tk.Frame(quality_section, bg=Theme.CARD)
        method_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(method_frame, text="Quality Calculation Method:", font=Theme.f(9, 'bold'),
                 bg=Theme.CARD, fg=Theme.TEXT).pack(side=tk.LEFT)
        
        self.quality_method = tk.StringVar(value="leaf_count")
        tk.Radiobutton(method_frame, text="Leaf Count", variable=self.quality_method, 
                      value="leaf_count", bg=Theme.CARD, font=Theme.f(9),
                      command=self.toggle_quality_method).pack(side=tk.LEFT, padx=(10, 5))
        tk.Radiobutton(method_frame, text="Weight-Based", variable=self.quality_method,
                      value="weight_based", bg=Theme.CARD, font=Theme.f(9),
                      command=self.toggle_quality_method).pack(side=tk.LEFT, padx=5)
        
        # Leaf count section (visible by default)
        self.counts_frame = tk.Frame(quality_section, bg=Theme.CARD)
        self.counts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a grid with 2 columns (Good and Bad)
        counts_grid = tk.Frame(self.counts_frame, bg=Theme.CARD)
        counts_grid.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # GOOD LEAVES - Left column
        good_frame = tk.LabelFrame(counts_grid, text="✅ GOOD LEAVES", 
                                   font=Theme.f(9, 'bold'), bg=Theme.SUCCESS_BG,
                                   fg=Theme.SUCCESS, padx=10, pady=8)
        good_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        self.good_entries = {}
        for i, (key, label) in enumerate(GOOD_CATEGORIES):
            row = tk.Frame(good_frame, bg=Theme.SUCCESS_BG)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label + ":", font=Theme.f(12), bg=Theme.SUCCESS_BG, fg=Theme.TEXT).pack(side=tk.LEFT)
            e = tk.Entry(row, width=10, font=Theme.f(13), relief='flat', bg=Theme.CARD,
                         highlightthickness=1, highlightbackground=Theme.BORDER, justify='center')
            e.pack(side=tk.RIGHT, ipady=3)
            e.bind('<KeyRelease>', self.calculate_quality)
            e.bind('<Tab>', self.on_tab_pressed)
            self.count_entries[key] = e
            self.good_entries[key] = e
        
        # BAD LEAVES - Right column
        bad_frame = tk.LabelFrame(counts_grid, text="❌ BAD LEAVES", 
                                  font=Theme.f(9, 'bold'), bg=Theme.DANGER_BG,
                                  fg=Theme.DANGER, padx=10, pady=8)
        bad_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        self.bad_entries = {}
        for i, (key, label) in enumerate(BAD_CATEGORIES):
            row = tk.Frame(bad_frame, bg=Theme.DANGER_BG)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label + ":", font=Theme.f(10), bg=Theme.DANGER_BG, fg=Theme.TEXT).pack(side=tk.LEFT)
            e = tk.Entry(row, width=10, font=Theme.f(11), relief='flat', bg=Theme.CARD,
                         highlightthickness=1, highlightbackground=Theme.BORDER, justify='center')
            e.pack(side=tk.RIGHT, ipady=3)
            e.bind('<KeyRelease>', self.calculate_quality)
            e.bind('<Tab>', self.on_tab_pressed)
            self.count_entries[key] = e
            self.bad_entries[key] = e
        
        # Configure grid weights
        counts_grid.grid_columnconfigure(0, weight=1)
        counts_grid.grid_columnconfigure(1, weight=1)
        counts_grid.grid_rowconfigure(0, weight=1)
        
        # Weight-based section (hidden by default)
        self.weight_frame = tk.Frame(quality_section, bg=Theme.CARD)
        self.weight_frame.pack(fill=tk.X, pady=10)
        self.weight_frame.pack_forget()
        
        weight_grid = tk.Frame(self.weight_frame, bg=Theme.CARD)
        weight_grid.pack(pady=10)
        
        # Good weight - left
        good_w_frame = tk.LabelFrame(weight_grid, text="✅ GOOD LEAVES WEIGHT", 
                                      font=Theme.f(9, 'bold'), bg=Theme.SUCCESS_BG,
                                      fg=Theme.SUCCESS, padx=10, pady=8)
        good_w_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        tk.Label(good_w_frame, text="Weight (grams):", font=Theme.f(12), bg=Theme.SUCCESS_BG).pack(anchor='w')
        self.good_weight_entry = tk.Entry(good_w_frame, width=15, font=Theme.f(14), relief='flat',
                                          bg=Theme.CARD, highlightthickness=1, highlightbackground=Theme.BORDER)
        self.good_weight_entry.pack(pady=5, ipady=4)
        self.good_weight_entry.bind('<KeyRelease>', self.calculate_quality_weight)
        self.good_weight_entry.bind('<Tab>', self.on_tab_pressed)
        
        # Bad weight - right
        bad_w_frame = tk.LabelFrame(weight_grid, text="❌ BAD LEAVES WEIGHT", 
                                     font=Theme.f(9, 'bold'), bg=Theme.DANGER_BG,
                                     fg=Theme.DANGER, padx=10, pady=8)
        bad_w_frame.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        
        tk.Label(bad_w_frame, text="Weight (grams):", font=Theme.f(12), bg=Theme.DANGER_BG).pack(anchor='w')
        self.bad_weight_entry = tk.Entry(bad_w_frame, width=15, font=Theme.f(14), relief='flat',
                                         bg=Theme.CARD, highlightthickness=1, highlightbackground=Theme.BORDER)
        self.bad_weight_entry.pack(pady=5, ipady=4)
        self.bad_weight_entry.bind('<KeyRelease>', self.calculate_quality_weight)
        self.bad_weight_entry.bind('<Tab>', self.on_tab_pressed)
        
        weight_grid.grid_columnconfigure(0, weight=1)
        weight_grid.grid_columnconfigure(1, weight=1)
        weight_grid.grid_rowconfigure(0, weight=1)

        ttk.Separator(form, orient='horizontal').pack(fill=tk.X, pady=16)

        result_row = tk.Frame(form, bg=Theme.CARD)
        result_row.pack(fill=tk.X)

        # BUTTONS - Left side (SAVE + CLEAR)
        btn_frame = tk.Frame(result_row, bg=Theme.CARD)
        btn_frame.pack(side=tk.LEFT, anchor='w')
        make_button(btn_frame, "💾 SAVE BATCH", self.save_batch, kind="success", pady=6, padx=16).pack(side=tk.LEFT)
        make_button(btn_frame, "🗑 CLEAR", self.clear_form, kind="neutral", pady=6, padx=16).pack(side=tk.LEFT, padx=(5, 0))

        # Totals - Middle
        totals_box = tk.Frame(result_row, bg=Theme.CARD)
        totals_box.pack(side=tk.LEFT, anchor='w', padx=(15, 0))
        self.totals_label = tk.Label(totals_box, text="Good: 0     Bad: 0     Total Leaves: 0",
                                      font=Theme.f(13), bg=Theme.CARD, fg=Theme.TEXT_MUTED)
        self.totals_label.pack(anchor='w')

        # Quality - Right side
        quality_box = tk.Frame(result_row, bg=Theme.BG, highlightbackground=Theme.BORDER, highlightthickness=1)
        quality_box.pack(side=tk.RIGHT, padx=(10, 0), ipadx=16, ipady=6)
        tk.Label(quality_box, text="QUALITY", font=Theme.f(13, 'bold'), bg=Theme.BG, fg=Theme.TEXT_MUTED).pack()
        self.quality_label = tk.Label(quality_box, text="0.0%", font=Theme.f(22, 'bold'), bg=Theme.BG, fg=Theme.TEXT_MUTED)
        self.quality_label.pack()
        self.status_label = tk.Label(quality_box, text="", font=Theme.f(11, 'bold'), bg=Theme.BG)
        self.status_label.pack()

    def toggle_quality_method(self):
        if self.quality_method.get() == "leaf_count":
            self.counts_frame.pack(fill=tk.BOTH, expand=True)
            self.weight_frame.pack_forget()
            self.calculate_quality()
        else:
            self.counts_frame.pack_forget()
            self.weight_frame.pack(fill=tk.X, pady=10)
            self.calculate_quality_weight()

    def on_tab_pressed(self, event):
        """Handle Tab key navigation and auto-save if on last field"""
        current = event.widget
        
        if current == self.bad_weight_entry or current == list(self.count_entries.values())[-1]:
            self.save_batch()
            return "break"
        
        entries = list(self.count_entries.values())
        if current in entries and entries.index(current) == len(entries) - 1:
            self.save_batch()
            return "break"
        
        return None

    def create_stats_panel(self, parent):
        outer, stats_frame = card_frame(parent, padx=20, pady=20)
        outer.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        outer.config(width=420)

        section_label(stats_frame, "TODAY'S STATISTICS", "\U0001F4CA").pack(anchor='w', pady=(0, 12))

        self.stats_container = tk.Frame(stats_frame, bg=Theme.CARD)
        self.stats_container.pack(fill=tk.BOTH, expand=True)

        btn_col = tk.Frame(stats_frame, bg=Theme.CARD)
        btn_col.pack(fill=tk.X, pady=(15, 0))
    
        make_button(btn_col, "\U0001F4C4  Generate Report", self.show_report_dialog, kind="success").pack(fill=tk.X, pady=(0, 8))
    
        if self.is_admin:
            make_button(btn_col, "\U0001F3E2  Manage Centers", self.manage_buying_centers, kind="primary").pack(fill=tk.X, pady=(0, 5))
            make_button(btn_col, "\U0001F69A  Manage Trucks", self.manage_trucks, kind="primary").pack(fill=tk.X, pady=(0, 5))
            make_button(btn_col, "\U0001F464  Manage Users", self.manage_users, kind="primary").pack(fill=tk.X, pady=(0, 5))
            make_button(btn_col, "\U0001F4CA  Admin Dashboard", self.show_admin_dashboard, kind="primary").pack(fill=tk.X, pady=(0, 8))

    def create_recent_batches(self, parent):
        outer, recent_frame = card_frame(parent, padx=15, pady=15)
        outer.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, pady=(15, 0))

        section_label(recent_frame, "RECENT BATCHES (Last 10)", "\U0001F553").pack(anchor='w', pady=(0, 10))

        table_frame = tk.Frame(recent_frame, bg=Theme.CARD)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Batch ID', 'Center', 'Truck', 'Total kg', 'Quality', 'Time', 'Method')
        self.recent_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=6)
        for col in columns:
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=130, anchor='center')
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.recent_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.recent_tree.configure(yscrollcommand=scrollbar.set)

    # ---------------- data loading ----------------
    def load_data(self):
        self.center_combo['values'] = self.db.get_center_names()
        self.truck_combo['values'] = self.db.get_truck_registrations()
        self.update_stats()
        self.load_recent_batches()

    def on_center_selected(self, event=None):
        center = self.center_combo.get()
        if center:
            today = datetime.now().strftime('%Y-%m-%d')
            preview_id = self.db.generate_batch_id(center, today)
            self.batch_id_label.config(text=preview_id)

    def on_truck_selected(self, event=None):
        truck_reg = self.truck_combo.get()
        if truck_reg:
            driver = self.db.get_driver_by_truck(truck_reg)
            if driver:
                self.driver_entry.config(state='normal')
                self.driver_entry.delete(0, tk.END)
                self.driver_entry.insert(0, driver)
                self.driver_entry.config(state='readonly')

    # ---------------- quality calculation ----------------
    def _read_counts(self):
        counts = {}
        for key, _ in ALL_CATEGORIES:
            raw = self.count_entries[key].get().strip()
            counts[key] = int(raw) if raw.isdigit() else 0
        return counts

    def calculate_quality(self, event=None):
        counts = self._read_counts()
        good = sum(counts[k] for k, _ in GOOD_CATEGORIES)
        bad = sum(counts[k] for k, _ in BAD_CATEGORIES)
        total = good + bad

        self.totals_label.config(text=f"Good: {good}     Bad: {bad}     Total Leaves: {total}",
                             font=Theme.f(12, 'bold'))

        box = self.quality_label.master
        if total > 0:
            quality = (good / total) * 100
            tier, color, bg, symbol = quality_tier(quality)
            self.quality_label.config(text=f"{quality:.1f}%", fg=color, font=Theme.f(32, 'bold'))
            self.status_label.config(text=f"{symbol} {tier}", font=Theme.f(14, 'bold'), fg=color)
            box.config(bg=bg, highlightbackground=color, highlightthickness=3)
            for child in box.winfo_children():
                child.config(bg=bg)
        else:
            self.quality_label.config(text="0.0%", fg=Theme.TEXT_MUTED, font=Theme.f(32, 'bold'))
            self.status_label.config(text="", font=Theme.f(14, 'bold'))
            box.config(bg=Theme.BG, highlightbackground=Theme.BORDER, highlightthickness=1)
            for child in box.winfo_children():
                child.config(bg=Theme.BG)

    def calculate_quality_weight(self, event=None):
        try:
            good_weight = float(self.good_weight_entry.get().strip() or 0)
            bad_weight = float(self.bad_weight_entry.get().strip() or 0)
        except ValueError:
            good_weight = bad_weight = 0

        total_weight = good_weight + bad_weight
        self.totals_label.config(text=f"Good: {good_weight:.1f}g     Bad: {bad_weight:.1f}g     Total: {total_weight:.1f}g",
                             font=Theme.f(12, 'bold'))

        box = self.quality_label.master
        if total_weight > 0:
            quality = (good_weight / total_weight) * 100
            tier, color, bg, symbol = quality_tier(quality)
            self.quality_label.config(text=f"{quality:.1f}%", fg=color, font=Theme.f(32, 'bold'))
            self.status_label.config(text=f"{symbol} {tier}", font=Theme.f(14, 'bold'), fg=color)
            box.config(bg=bg, highlightbackground=color, highlightthickness=3)
            for child in box.winfo_children():
                child.config(bg=bg)
        else:
            self.quality_label.config(text="0.0%", fg=Theme.TEXT_MUTED, font=Theme.f(32, 'bold'))
            self.status_label.config(text="", font=Theme.f(14, 'bold'))
            box.config(bg=Theme.BG, highlightbackground=Theme.BORDER, highlightthickness=1)
            for child in box.winfo_children():
                child.config(bg=Theme.BG)

    # ---------------- set status ----------------
    def set_status(self, message):
        self.status_var.set(message)

    # ---------------- save ----------------
    def save_batch(self):
        center = self.center_combo.get()
        truck = self.truck_combo.get()
        driver = self.driver_entry.get()

        if not center or not truck or not driver:
            messagebox.showerror("Error", "Please select a Buying Center and a Truck.")
            return

        try:
            total_kg = float(self.total_kg_entry.get())
            if total_kg <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Total Weight Delivered (kg), greater than 0.")
            return

        method = self.quality_method.get()
        
        if method == "leaf_count":
            counts = self._read_counts()
            good = sum(counts[k] for k, _ in GOOD_CATEGORIES)
            bad = sum(counts[k] for k, _ in BAD_CATEGORIES)
            total_leaves = good + bad

            if total_leaves == 0:
                messagebox.showerror("Error", "Please enter at least one leaf count.")
                return

            quality = (good / total_leaves) * 100
            data = {
                **counts,
                'total_good': good,
                'total_bad': bad,
                'total_leaves': total_leaves,
            }
        else:  # weight_based
            try:
                good_weight = float(self.good_weight_entry.get().strip() or 0)
                bad_weight = float(self.bad_weight_entry.get().strip() or 0)
                if good_weight <= 0 and bad_weight <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Please enter valid weights for good and bad leaves.")
                return

            total_weight = good_weight + bad_weight
            quality = (good_weight / total_weight) * 100
            data = {
                'leaf_1bud': 0,
                'leaf_2bud': 0,
                'soft_bhanji': 0,
                'leaf_3bud': 0,
                'hard_leaf': 0,
                'loose_leaves': 0,
                'stalky_bruised': 0,
                'stems_stalks': 0,
                'total_good': 0,
                'total_bad': 0,
                'total_leaves': 0,
            }

        today = datetime.now().strftime('%Y-%m-%d')
        batch_id = self.db.generate_batch_id(center, today)

        full_data = {
            'batch_id': batch_id,
            'date': today,
            'buying_center': center,
            'truck_registration': truck,
            'driver_name': driver,
            'total_kg': total_kg,
            **data,
            'quality_percent': quality,
            'quality_method': method,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'entered_by': self.user['username'],
        }

        try:
            # SAVE TO DATABASE
            self.db.save_batch(full_data)
            
            # Show success message
            tier, _, _, _ = quality_tier(quality)
            messagebox.showinfo("Success", f"✅ Batch {batch_id} saved!\nQuality: {quality:.1f}% ({tier})")
            
            # Update status bar
            self.set_status(f"Saved batch {batch_id}  |  Quality {quality:.1f}% ({tier})")
            
            # CLEAR THE FORM
            self.clear_form()
            
            # REFRESH EVERYTHING - THIS IS WHAT YOU WANT
            self.update_stats()          # Updates daily reports/stats
            self.load_recent_batches()   # Updates recent batches table
            
            # Generate a new batch ID for next entry
            center = self.center_combo.get()
            if center:
                today = datetime.now().strftime('%Y-%m-%d')
                new_id = self.db.generate_batch_id(center, today)
                self.batch_id_label.config(text=new_id)
            else:
                self.batch_id_label.config(text="-- select a center --")
                
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Batch ID '{batch_id}' already exists. Please try again.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def clear_form(self):
        self.center_combo.set('')
        self.truck_combo.set('')
        self.driver_entry.config(state='normal')
        self.driver_entry.delete(0, tk.END)
        self.driver_entry.config(state='readonly')
        self.batch_id_label.config(text="-- select a center --")
        self.total_kg_entry.delete(0, tk.END)
        for e in self.count_entries.values():
            e.delete(0, tk.END)
        self.good_weight_entry.delete(0, tk.END)
        self.bad_weight_entry.delete(0, tk.END)
        self.quality_method.set("leaf_count")
        self.toggle_quality_method()
        self.calculate_quality()
        self.center_combo.focus()

    # ---------------- dashboard stats ----------------
    def update_stats(self):
        for child in self.stats_container.winfo_children():
            child.destroy()

        today = datetime.now().strftime('%Y-%m-%d')
        stats = self.db.get_today_stats(today)
        best_center, worst_center = self.db.get_best_worst(today, 'buying_center')
        best_truck, worst_truck = self.db.get_best_worst(today, 'truck_registration')

        def stat_row(label, value, color=Theme.TEXT):
            r = tk.Frame(self.stats_container, bg=Theme.CARD)
            r.pack(fill=tk.X, pady=3)
            tk.Label(r, text=label, font=Theme.f(11), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(side=tk.LEFT)
            tk.Label(r, text=value, font=Theme.f(12, 'bold'), bg=Theme.CARD, fg=color).pack(side=tk.RIGHT)

        tk.Label(self.stats_container, text=today, font=Theme.f(11, 'bold'), bg=Theme.CARD, fg=Theme.PRIMARY).pack(anchor='w', pady=(0, 8))
        stat_row("Batches (samples)", str(stats['count']))
        stat_row("Total Tea (kg)", f"{stats['total_kg']:,.1f}")
        stat_row("Average Quality", f"{stats['avg_quality']:.1f}%",
                  color=quality_tier(stats['avg_quality'])[1] if stats['count'] else Theme.TEXT_MUTED)

        ttk.Separator(self.stats_container, orient='horizontal').pack(fill=tk.X, pady=10)

        def leaderboard(title, best, worst, icon_best="\U0001F3C6", icon_worst="\u26a0"):
            tk.Label(self.stats_container, text=title, font=Theme.f(11, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(2, 4))
            if best:
                tk.Label(self.stats_container, text=f"{icon_best} Best: {best[0]}  \u2014  {best[1]:.1f}%",
                         font=Theme.f(11), bg=Theme.CARD, fg=Theme.SUCCESS).pack(anchor='w')
            else:
                tk.Label(self.stats_container, text="No data yet", font=Theme.f(11), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack(anchor='w')
            if worst:
                tk.Label(self.stats_container, text=f"{icon_worst} Needs attention: {worst[0]}  \u2014  {worst[1]:.1f}%",
                         font=Theme.f(11), bg=Theme.CARD, fg=Theme.DANGER).pack(anchor='w', pady=(0, 8))

        leaderboard("BUYING CENTERS TODAY", best_center, worst_center)
        leaderboard("TRUCKS TODAY", best_truck, worst_truck)

    def load_recent_batches(self):
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)

        for row in self.db.get_recent_batches(10):
            quality = row[4]
            _, _, bg, _ = quality_tier(quality)
            display_row = list(row)
            display_row[3] = f"{display_row[3]:,.1f}"
            display_row[4] = f"{quality:.1f}%"
            display_row = display_row[:7]
            self.recent_tree.insert('', tk.END, values=display_row, tags=(bg,))
            self.recent_tree.tag_configure(bg, background=bg)

    # ---------------- report dialog ----------------
    def show_report_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Generate Report")
        win.geometry("500x450")
        win.configure(bg=Theme.BG)
        win.transient(self.root)
        win.grab_set()

        outer, card = card_frame(win, padx=25, pady=20)
        outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        section_label(card, "REPORT OPTIONS", "\U0001F4C4").pack(anchor='w', pady=(0, 15))

        # Report type
        tk.Label(card, text="Report Type:", font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(10, 3))
        report_type = ttk.Combobox(card, values=['General', 'By Center', 'By Truck'], state='readonly', font=Theme.f(10))
        report_type.set('General')
        report_type.pack(fill=tk.X, ipady=3)

        # Date range
        tk.Label(card, text="Date Range:", font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(10, 3))
        
        date_frame = tk.Frame(card, bg=Theme.CARD)
        date_frame.pack(fill=tk.X)
        
        tk.Label(date_frame, text="From:", font=Theme.f(9), bg=Theme.CARD).pack(side=tk.LEFT, padx=(0, 5))
        from_date = tk.Entry(date_frame, width=12, font=Theme.f(9), relief='flat',
                            bg="#eef2f0", highlightthickness=1, highlightbackground=Theme.BORDER)
        from_date.pack(side=tk.LEFT, padx=(0, 10))
        from_date.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
        tk.Label(date_frame, text="To:", font=Theme.f(9), bg=Theme.CARD).pack(side=tk.LEFT, padx=(0, 5))
        to_date = tk.Entry(date_frame, width=12, font=Theme.f(9), relief='flat',
                          bg="#eef2f0", highlightthickness=1, highlightbackground=Theme.BORDER)
        to_date.pack(side=tk.LEFT)
        to_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Filter selection
        tk.Label(card, text="Filter (for By Center/By Truck):", font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(10, 3))
        
        filter_frame = tk.Frame(card, bg=Theme.CARD)
        filter_frame.pack(fill=tk.X)
        
        self.filter_combo = ttk.Combobox(filter_frame, width=30, font=Theme.f(10), state='readonly')
        self.filter_combo.pack(fill=tk.X, ipady=3)
        self.filter_combo.set("Select a center or truck...")
        
        def update_filter(*args):
            if report_type.get() == "By Center":
                self.filter_combo['values'] = self.db.get_center_names()
                self.filter_combo.set('')
                self.filter_combo.config(state='readonly')
            elif report_type.get() == "By Truck":
                self.filter_combo['values'] = self.db.get_truck_registrations()
                self.filter_combo.set('')
                self.filter_combo.config(state='readonly')
            else:
                self.filter_combo['values'] = []
                self.filter_combo.set("Not needed for General report")
                self.filter_combo.config(state='disabled')
        
        report_type.bind('<<ComboboxSelected>>', update_filter)
        update_filter()

        # Generate button
        def generate_report():
            r_type = report_type.get()
            from_str = from_date.get().strip()
            to_str = to_date.get().strip()
            
            if not from_str or not to_str:
                messagebox.showerror("Error", "Please enter valid dates.")
                return
            
            try:
                datetime.strptime(from_str, '%Y-%m-%d')
                datetime.strptime(to_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Please use YYYY-MM-DD date format.")
                return
            
            filter_value = None
            if r_type == "By Center":
                filter_value = self.filter_combo.get()
                if not filter_value or filter_value in ["Select a center or truck...", "Not needed for General report"]:
                    messagebox.showerror("Error", "Please select a buying center.")
                    return
            elif r_type == "By Truck":
                filter_value = self.filter_combo.get()
                if not filter_value or filter_value in ["Select a center or truck...", "Not needed for General report"]:
                    messagebox.showerror("Error", "Please select a truck.")
                    return
            
            try:
                rows = self.db.get_batches_between(from_str, to_str, 
                                                filter_value if r_type == "By Center" else None,
                                                filter_value if r_type == "By Truck" else None)
                
                title = f"TEA RECEPTION QUALITY REPORT - {r_type.upper()}"
                period = f"Period: {from_str} to {to_str}"
                report = build_aggregate_report(rows, title, period, 
                                              filter_value if r_type == "By Center" else None,
                                              filter_value if r_type == "By Truck" else None)
                
                win.destroy()
                self._show_report_window(f"{r_type} Report", report, 
                                       f"{r_type.lower()}_report_{from_str}_to_{to_str}.txt")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

        make_button(card, "GENERATE REPORT", generate_report, kind="success").pack(fill=tk.X, pady=(20, 0))
        make_button(card, "Cancel", win.destroy, kind="neutral").pack(fill=tk.X, pady=(5, 0))

    def _show_report_window(self, title, report_text, default_filename):
        try:
            win = tk.Toplevel(self.root)
            win.title(title)
            win.geometry("1050x680")
            win.configure(bg=Theme.BG)

            header = tk.Frame(win, bg=Theme.PRIMARY, height=50)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            tk.Label(header, text=title, font=Theme.f(13, 'bold'), bg=Theme.PRIMARY, fg="white").pack(side=tk.LEFT, padx=20)

            body = tk.Frame(win, bg=Theme.BG)
            body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

            text_outer, text_card = card_frame(body, padx=0, pady=0)
            text_outer.pack(fill=tk.BOTH, expand=True)

            text_widget = tk.Text(text_card, font=('Courier New', 9), wrap=tk.NONE, bg=Theme.CARD,
                                   relief='flat', padx=15, pady=15)
            text_widget.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
            text_widget.insert('1.0', report_text)
            text_widget.config(state='disabled')

            vscroll = ttk.Scrollbar(text_card, orient=tk.VERTICAL, command=text_widget.yview)
            vscroll.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.configure(yscrollcommand=vscroll.set)

            hscroll = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=text_widget.xview)
            hscroll.pack(side=tk.BOTTOM, fill=tk.X, padx=15)
            text_widget.configure(xscrollcommand=hscroll.set)

            btn_frame = tk.Frame(win, bg=Theme.BG)
            btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 12))

            def save_to_file():
                path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt")],
                    initialdir=REPORTS_DIR,
                    initialfile=default_filename
                )
                if path:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(report_text)
                    messagebox.showinfo("Saved", f"Report saved to:\n{path}")
                    return path
                return None

            def save_and_print():
                path = save_to_file()
                if not path:
                    return
                if sys.platform.startswith('win'):
                    try:
                        os.startfile(path, "print")
                        messagebox.showinfo("Printing", "Sent to default printer.")
                    except Exception as e:
                        messagebox.showwarning("Print", f"Could not auto-print ({e}). Please open the saved file and print it manually.")
                else:
                    messagebox.showinfo("Print", "Please open the saved text file and print it from there.")

            make_button(btn_frame, "\U0001F4BE  Save to File", save_to_file, kind="success").pack(side=tk.LEFT, padx=15)
            make_button(btn_frame, "\U0001F5A8  Save & Print", save_and_print, kind="primary").pack(side=tk.LEFT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display report: {str(e)}")
    def backup_database(self):
        backup_file = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database files", "*.db")],
            initialdir=BACKUP_DIR,
            initialfile=f"tea_factory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        if backup_file:
            try:
                self.db.close()
                shutil.copy2(DB_FILE, backup_file)
                self.db.connect()
                messagebox.showinfo("Success", f"Database backed up to {backup_file}")
            except Exception as e:
                messagebox.showerror("Error", f"Backup failed: {str(e)}")

    # ---------------- admin dialog helper ----------------
    def _styled_toplevel(self, title, size):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(size)
        win.configure(bg=Theme.BG)
        return win

    def _dialog_field(self, parent, label_text):
        tk.Label(parent, text=label_text, font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(12, 3))
        e = tk.Entry(parent, font=Theme.f(10), relief='flat', bg="#eef2f0",
                     highlightthickness=1, highlightbackground=Theme.BORDER)
        e.pack(fill=tk.X, ipady=6)
        return e

    # ---------------- admin: buying centers ----------------
    def manage_buying_centers(self):
        if not self.is_admin:
            return
        win = self._styled_toplevel("Manage Buying Centers", "900x550")

        body = tk.Frame(win, bg=Theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        section_label(body, "BUYING CENTERS", "\U0001F3E2").pack(anchor='w', pady=(0, 10))

        table_outer, table_card = card_frame(body, padx=0, pady=0)
        table_outer.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Code', 'Location', 'Contact', 'Phone')
        tree = ttk.Treeview(table_card, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)
        tree.pack(fill=tk.BOTH, expand=True)

        def refresh():
            tree.delete(*tree.get_children())
            for r in self.db.get_all_centers_full():
                tree.insert('', tk.END, values=tuple(r))
        refresh()

        btn_frame = tk.Frame(win, bg=Theme.BG)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        def add_dialog():
            d = self._styled_toplevel("Add Buying Center", "400x450")
            outer, card = card_frame(d, padx=25, pady=20)
            outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            fields = {}
            for label in ["Name", "Location", "Contact Person", "Phone"]:
                fields[label] = self._dialog_field(card, label)

            def do_save():
                name = fields["Name"].get().strip()
                if not name:
                    messagebox.showerror("Error", "Name is required")
                    return
                try:
                    self.db.add_buying_center(name, fields["Location"].get(),
                                               fields["Contact Person"].get(), fields["Phone"].get())
                    refresh()
                    self.load_data()
                    d.destroy()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Buying center already exists")

            make_button(card, "Save", do_save, kind="success").pack(fill=tk.X, pady=(20, 0))

        def edit_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a buying center to edit.")
                return
            values = tree.item(sel[0])['values']
            
            d = self._styled_toplevel("Edit Buying Center", "400x450")
            outer, card = card_frame(d, padx=25, pady=20)
            outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            
            fields = {}
            for label in ["Name", "Location", "Contact Person", "Phone"]:
                fields[label] = self._dialog_field(card, label)
            
            fields["Name"].insert(0, values[1])
            fields["Location"].insert(0, values[3] if values[3] else "")
            fields["Contact Person"].insert(0, values[4] if values[4] else "")
            fields["Phone"].insert(0, values[5] if values[5] else "")

            def do_update():
                name = fields["Name"].get().strip()
                if not name:
                    messagebox.showerror("Error", "Name is required")
                    return
                try:
                    self.db.update_buying_center(values[0], name, fields["Location"].get(),
                                                fields["Contact Person"].get(), fields["Phone"].get())
                    refresh()
                    self.load_data()
                    d.destroy()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Buying center name already exists")

            make_button(card, "Update", do_update, kind="success").pack(fill=tk.X, pady=(20, 0))

        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a buying center to delete.")
                return
            values = tree.item(sel[0])['values']
            if messagebox.askyesno("Confirm Delete", f"Delete buying center '{values[1]}'?\n(Existing batch records referencing it are kept.)"):
                self.db.delete_buying_center(values[0])
                refresh()
                self.load_data()

        make_button(btn_frame, "+ Add Center", add_dialog, kind="success").pack(side=tk.LEFT, padx=(0, 5))
        make_button(btn_frame, "Edit Center", edit_selected, kind="primary").pack(side=tk.LEFT, padx=(0, 5))
        make_button(btn_frame, "\U0001F5D1 Delete Selected", delete_selected, kind="danger").pack(side=tk.LEFT)

    # ---------------- admin: trucks ----------------
    def manage_trucks(self):
        if not self.is_admin:
            return
        win = self._styled_toplevel("Manage Trucks & Drivers", "900x550")

        body = tk.Frame(win, bg=Theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        section_label(body, "TRUCKS & DRIVERS", "\U0001F69A").pack(anchor='w', pady=(0, 10))

        table_outer, table_card = card_frame(body, padx=0, pady=0)
        table_outer.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Registration', 'Driver', 'Driver Phone', 'Owner')
        tree = ttk.Treeview(table_card, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        tree.pack(fill=tk.BOTH, expand=True)

        def refresh():
            tree.delete(*tree.get_children())
            for r in self.db.get_all_trucks_full():
                tree.insert('', tk.END, values=tuple(r))
        refresh()

        btn_frame = tk.Frame(win, bg=Theme.BG)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        def add_dialog():
            d = self._styled_toplevel("Add Truck", "400x480")
            outer, card = card_frame(d, padx=25, pady=20)
            outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            fields = {}
            for label in ["Registration", "Driver Name", "Driver Phone", "Owner Name"]:
                fields[label] = self._dialog_field(card, label)

            def do_save():
                reg = fields["Registration"].get().strip().upper()
                driver = fields["Driver Name"].get().strip()
                if not reg or not driver:
                    messagebox.showerror("Error", "Registration and Driver Name are required")
                    return
                try:
                    self.db.add_truck(reg, driver, fields["Driver Phone"].get(), fields["Owner Name"].get())
                    refresh()
                    self.load_data()
                    d.destroy()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Truck registration already exists")

            make_button(card, "Save", do_save, kind="success").pack(fill=tk.X, pady=(20, 0))

        def edit_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a truck to edit.")
                return
            values = tree.item(sel[0])['values']
            
            d = self._styled_toplevel("Edit Truck", "400x480")
            outer, card = card_frame(d, padx=25, pady=20)
            outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            
            fields = {}
            for label in ["Registration", "Driver Name", "Driver Phone", "Owner Name"]:
                fields[label] = self._dialog_field(card, label)
            
            fields["Registration"].insert(0, values[1])
            fields["Driver Name"].insert(0, values[2])
            fields["Driver Phone"].insert(0, values[3] if values[3] else "")
            fields["Owner Name"].insert(0, values[4] if values[4] else "")

            def do_update():
                reg = fields["Registration"].get().strip().upper()
                driver = fields["Driver Name"].get().strip()
                if not reg or not driver:
                    messagebox.showerror("Error", "Registration and Driver Name are required")
                    return
                try:
                    self.db.update_truck(values[0], reg, driver, fields["Driver Phone"].get(),
                                        fields["Owner Name"].get())
                    refresh()
                    self.load_data()
                    d.destroy()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Truck registration already exists")

            make_button(card, "Update", do_update, kind="success").pack(fill=tk.X, pady=(20, 0))

        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a truck to delete.")
                return
            values = tree.item(sel[0])['values']
            if messagebox.askyesno("Confirm Delete", f"Delete truck '{values[1]}'?\n(Existing batch records referencing it are kept.)"):
                self.db.delete_truck(values[0])
                refresh()
                self.load_data()

        make_button(btn_frame, "+ Add Truck", add_dialog, kind="success").pack(side=tk.LEFT, padx=(0, 5))
        make_button(btn_frame, "Edit Truck", edit_selected, kind="primary").pack(side=tk.LEFT, padx=(0, 5))
        make_button(btn_frame, "\U0001F5D1 Delete Selected", delete_selected, kind="danger").pack(side=tk.LEFT)

    # ---------------- admin: users ----------------
    def manage_users(self):
        if not self.is_admin:
            return
        win = self._styled_toplevel("Manage Users", "560x480")

        body = tk.Frame(win, bg=Theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        section_label(body, "USERS", "\U0001F464").pack(anchor='w', pady=(0, 10))

        table_outer, table_card = card_frame(body, padx=0, pady=0)
        table_outer.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Username', 'Role')
        tree = ttk.Treeview(table_card, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        tree.pack(fill=tk.BOTH, expand=True)

        def refresh():
            tree.delete(*tree.get_children())
            for r in self.db.get_all_users():
                tree.insert('', tk.END, values=tuple(r))
        refresh()

        btn_frame = tk.Frame(win, bg=Theme.BG)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        def add_dialog():
            d = self._styled_toplevel("Add User", "360x420")
            outer, card = card_frame(d, padx=25, pady=20)
            outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

            u_entry = self._dialog_field(card, "Username")
            p_entry = self._dialog_field(card, "Password")

            tk.Label(card, text="Role", font=Theme.f(9, 'bold'), bg=Theme.CARD, fg=Theme.TEXT).pack(anchor='w', pady=(12, 3))
            role_combo = ttk.Combobox(card, values=['user', 'admin'], state='readonly', font=Theme.f(10))
            role_combo.set('user')
            role_combo.pack(fill=tk.X, ipady=3)

            def do_save():
                username = u_entry.get().strip()
                password = p_entry.get()
                role = role_combo.get()
                if not username or not password:
                    messagebox.showerror("Error", "Username and password are required")
                    return
                try:
                    self.db.add_user(username, password, role)
                    refresh()
                    d.destroy()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Username already exists")

            make_button(card, "Save", do_save, kind="success").pack(fill=tk.X, pady=(20, 0))

        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No selection", "Select a user to delete.")
                return
            values = tree.item(sel[0])['values']
            if values[1] == self.user['username']:
                messagebox.showerror("Error", "You cannot delete your own account while logged in.")
                return
            if values[2] == 'admin' and self.db.count_admins() <= 1:
                messagebox.showerror("Error", "Cannot delete the last remaining admin account.")
                return
            if messagebox.askyesno("Confirm Delete", f"Delete user '{values[1]}'?"):
                self.db.delete_user(values[0])
                refresh()

        make_button(btn_frame, "+ Add User", add_dialog, kind="success").pack(side=tk.LEFT, padx=(0, 10))
        make_button(btn_frame, "\U0001F5D1 Delete Selected", delete_selected, kind="danger").pack(side=tk.LEFT)

    # ---------------- admin dashboard ----------------
    def show_admin_dashboard(self):
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Admin privileges required.")
            return

        win = self._styled_toplevel("Admin Dashboard - All Administrative Tasks", "1100x700")

        body = tk.Frame(win, bg=Theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        section_label(body, "ADMIN DASHBOARD - FULL CONTROL PANEL", "\U0001F4CA").pack(anchor='w', pady=(0, 20))

        stats_frame = tk.Frame(body, bg=Theme.BG)
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        total_batches = len(self.db.get_all_batches())
        total_centers = len(self.db.get_all_centers_full())
        total_trucks = len(self.db.get_all_trucks_full())
        total_users = len(self.db.get_all_users())

        stats = [
            ("Total Batches", str(total_batches), Theme.PRIMARY),
            ("Buying Centers", str(total_centers), Theme.ACCENT),
            ("Trucks/Drivers", str(total_trucks), Theme.INFO),
            ("System Users", str(total_users), Theme.WARNING),
        ]

        for label, value, color in stats:
            card_outer, card = card_frame(stats_frame, padx=15, pady=15)
            card_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            
            tk.Label(card, text=value, font=Theme.f(28, 'bold'), bg=Theme.CARD, fg=color).pack()
            tk.Label(card, text=label, font=Theme.f(11), bg=Theme.CARD, fg=Theme.TEXT_MUTED).pack()

        section_label(body, "ADMINISTRATIVE TASKS", "\u2699").pack(anchor='w', pady=(10, 10))

        tasks_frame = tk.Frame(body, bg=Theme.BG)
        tasks_frame.pack(fill=tk.BOTH, expand=True)

        center_frame = tk.LabelFrame(tasks_frame, text="Buying Centers", font=Theme.f(12, 'bold'), 
                                 bg=Theme.CARD, fg=Theme.PRIMARY, padx=15, pady=15)
        center_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        make_button(center_frame, "Add New Center", self.manage_buying_centers, kind="success").pack(fill=tk.X, pady=5)
        make_button(center_frame, "Edit/Delete Centers", self.manage_buying_centers, kind="primary").pack(fill=tk.X, pady=5)
        tk.Label(center_frame, text="Manage all buying centers,\nadd new ones, or remove\nunused ones.", 
             font=Theme.f(10), bg=Theme.CARD, fg=Theme.TEXT_MUTED, justify='left').pack(pady=10)

        truck_frame = tk.LabelFrame(tasks_frame, text="Trucks & Drivers", font=Theme.f(12, 'bold'),
                               bg=Theme.CARD, fg=Theme.PRIMARY, padx=15, pady=15)
        truck_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        make_button(truck_frame, "Add New Truck", self.manage_trucks, kind="success").pack(fill=tk.X, pady=5)
        make_button(truck_frame, "Edit/Delete Trucks", self.manage_trucks, kind="primary").pack(fill=tk.X, pady=5)
        tk.Label(truck_frame, text="Manage truck fleet,\nassign drivers, update\ncontact information.", 
             font=Theme.f(10), bg=Theme.CARD, fg=Theme.TEXT_MUTED, justify='left').pack(pady=10)

        user_frame = tk.LabelFrame(tasks_frame, text="System Users", font=Theme.f(12, 'bold'),
                              bg=Theme.CARD, fg=Theme.PRIMARY, padx=15, pady=15)
        user_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

        make_button(user_frame, "Add New User", self.manage_users, kind="success").pack(fill=tk.X, pady=5)
        make_button(user_frame, "Delete Users", self.manage_users, kind="danger").pack(fill=tk.X, pady=5)
        tk.Label(user_frame, text="Create operator accounts,\nassign admin privileges,\nor remove users.", 
             font=Theme.f(10), bg=Theme.CARD, fg=Theme.TEXT_MUTED, justify='left').pack(pady=10)

        system_frame = tk.LabelFrame(tasks_frame, text="System Management", font=Theme.f(12, 'bold'),
                                bg=Theme.CARD, fg=Theme.PRIMARY, padx=15, pady=15)
        system_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        sys_btn_frame = tk.Frame(system_frame, bg=Theme.CARD)
        sys_btn_frame.pack(fill=tk.X)

        make_button(sys_btn_frame, "View All Batches", self.view_all_batches, kind="primary").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        make_button(sys_btn_frame, "Generate Reports", self.show_report_dialog, kind="primary").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        make_button(sys_btn_frame, "Backup Database", self.backup_database, kind="neutral").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        tasks_frame.grid_columnconfigure(0, weight=1)
        tasks_frame.grid_columnconfigure(1, weight=1)
        tasks_frame.grid_columnconfigure(2, weight=1)
        tasks_frame.grid_rowconfigure(0, weight=1)
        tasks_frame.grid_rowconfigure(1, weight=1)

    def view_all_batches(self):
        win = self._styled_toplevel("All Batches", "1200x600")

        body = tk.Frame(win, bg=Theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        section_label(body, "ALL BATCHES", "\U0001F4D6").pack(anchor='w', pady=(0, 10))

        table_outer, table_card = card_frame(body, padx=0, pady=0)
        table_outer.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Batch ID', 'Date', 'Center', 'Truck', 'Driver', 'Total kg', 
                  'Good', 'Bad', 'Leaves', 'Quality%', 'Method', 'By')
        tree = ttk.Treeview(table_card, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=90)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        for r in self.db.get_all_batches():
            quality = r['quality_percent']
            _, _, bg, _ = quality_tier(quality)
            tree.insert('', tk.END, values=tuple(r), tags=(bg,))
            tree.tag_configure(bg, background=bg)

    # ---------------- shortcuts help ----------------
    def show_shortcuts(self):
        shortcuts = """
KEYBOARD SHORTCUTS:

Ctrl+S - Save current batch
Tab    - Navigate through form fields
         (On last field, Tab triggers save)
Return - On login screen, submits credentials

Navigation:
- Use Tab to move between fields
- Use mouse to click any field
- Use arrow keys in dropdowns

Pro Tips:
1. Use leaf counting method for detailed quality analysis
2. Use weight-based method for faster batch processing
3. Generate reports with filters to analyze specific centers or trucks
4. Regular backups ensure data safety
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    # ---------------- help ----------------
    def show_user_guide(self):
        guide = """
TEA RECEPTION QUALITY TRACKING SYSTEM - USER GUIDE

ENTERING A NEW BATCH:

1. Select Buying Center - the Batch ID auto-generates
2. Select Truck Registration - Driver name auto-fills
3. Enter the Total Weight delivered by the truck (kg)

4. Choose Quality Calculation Method:
   - Leaf Count: Manual sorting and counting of leaves
   - Weight-Based: Weigh good vs bad leaves (faster)

5. For Leaf Count Method:
   - Take a 100g random sample from the truck's load
   - Sort by hand into the categories shown
   - Enter COUNT of leaves in each category

6. For Weight-Based Method:
   - Separate good and bad leaves from sample
   - Weigh each group in grams
   - Enter the weights in the provided fields

7. Quality % calculates automatically
8. Click SAVE BATCH or press Ctrl+S

REPORTS:

- Generate reports with filtering options:
  * General: All batches in date range
  * By Center: Focus on specific buying center
  * By Truck: Focus on specific truck/driver

- Reports include:
  * Factory-wide summaries
  * Per-center averages
  * Per-truck/driver averages
  * Daily trends
  * Full sample data listing

- Reports can be saved as text files or printed

ADMIN CAPABILITIES:

- Data menu > Manage Buying Centers:
  * Add, edit, or delete buying centers
  * Update contact information

- Data menu > Manage Trucks:
  * Add, edit, or delete trucks
  * Manage driver assignments

- Data menu > Manage Users:
  * Create or delete user accounts
  * Assign admin or operator roles

- Admin Dashboard:
  * Quick overview of system statistics
  * Quick access to management functions

BEST PRACTICES:

1. Always select correct center and truck
2. Ensure accurate leaf counting or weighing
3. Regular backups (File menu)
4. Generate daily reports for quality tracking
5. Review admin dashboard periodically
6. Keep user accounts secure

DEFAULT LOGINS:
  admin / admin123 (full access)
  operator / operator123 (batch entry only)
"""
        messagebox.showinfo("User Guide", guide)

    def show_about(self):
        about = f"""{APP_NAME}
Version {APP_VERSION}

Offline tea quality tracking by buying center, truck, and driver,
using leaf-counting and weight-based sampling methods.

NEW IN VERSION 3.0:
- Tab key support for saving batches (Ctrl+S)
- Weight-based quality calculation method
- Enhanced reporting with filters
- Full CRUD operations for centers and trucks
- Admin dashboard with system overview
- Improved role-based access control

Roles:
- admin: Full control including adding/deleting records
- user: Batch entry + reports

Default logins:
  admin / admin123
  operator / operator123
"""
        messagebox.showinfo("About", about)

    # ---------------- logout ----------------
    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.db.close()
            self.root.destroy()
            self.on_logout()


# ==================== APPLICATION LAUNCHER ====================
class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.current_user = None
        self.show_login()

    def show_login(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.config(menu=tk.Menu(self.root))
        LoginWindow(self.root, self.on_login_success)

    def on_login_success(self, user):
        self.current_user = user
        for widget in self.root.winfo_children():
            widget.destroy()
        TeaQualitySystem(self.root, user, on_logout=self.show_login)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = Application()
    app.run()