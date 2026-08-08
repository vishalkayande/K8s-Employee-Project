"""
Employee Directory - Kubernetes Training Project
--------------------------------------------------
A small Flask app that demonstrates a Python workload talking to two
backend services running as separate pods in Kubernetes:

  * MySQL   -> persistent storage for employee records
  * Redis   -> cache layer for the employee list + a live "page views" counter

Designed to be simple enough to read in one sitting, but realistic enough
to exercise Deployments, Services, Secrets, ConfigMaps, PVCs, init
containers, and liveness/readiness probes.
"""

import os
import time
import json
import logging

import pymysql
import redis
from flask import Flask, render_template, request, redirect, url_for, jsonify

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("employee-app")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration (populated via env vars -> ConfigMap / Secret in Kubernetes)
# ---------------------------------------------------------------------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "appuser")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "apppassword")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "employee_db")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 30))

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
POD_NAME = os.environ.get("POD_NAME", "unknown-pod")  # set via Downward API


# ---------------------------------------------------------------------------
# Connection helpers (with retry, since pods can start in any order)
# ---------------------------------------------------------------------------
def get_mysql_connection(retries=5, delay=2):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                connect_timeout=5,
                cursorclass=pymysql.cursors.DictCursor,
            )
            return conn
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("MySQL connection attempt %s/%s failed: %s", attempt, retries, e)
            time.sleep(delay)
    raise last_err


def get_redis_connection():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=3)


def init_db():
    """Create the employees table if it doesn't exist yet."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) NOT NULL,
                    department VARCHAR(100) NOT NULL,
                    salary DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    r = get_redis_connection()

    # Track total page views in Redis - a simple, visible proof that the
    # Redis pod is being used independently of MySQL.
    try:
        views = r.incr("page_views")
    except Exception as e:  # noqa: BLE001
        log.warning("Redis incr failed: %s", e)
        views = "N/A"

    cache_hit = False
    employees = None

    # Try the cache first
    try:
        cached = r.get("employees_cache")
        if cached:
            employees = json.loads(cached)
            cache_hit = True
    except Exception as e:  # noqa: BLE001
        log.warning("Redis get failed: %s", e)

    if employees is None:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM employees ORDER BY id DESC")
                employees = cur.fetchall()
                # Decimal isn't JSON serializable, cast to str
                for e in employees:
                    e["salary"] = str(e["salary"])
                    e["created_at"] = str(e["created_at"])
        finally:
            conn.close()

        try:
            r.setex("employees_cache", CACHE_TTL_SECONDS, json.dumps(employees))
        except Exception as e:  # noqa: BLE001
            log.warning("Redis setex failed: %s", e)

    return render_template(
        "index.html",
        employees=employees,
        cache_hit=cache_hit,
        views=views,
        pod_name=POD_NAME,
        app_version=APP_VERSION,
    )


@app.route("/add", methods=["GET", "POST"])
def add_employee():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        department = request.form["department"]
        salary = request.form.get("salary", 0)

        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO employees (name, email, department, salary) VALUES (%s, %s, %s, %s)",
                    (name, email, department, salary),
                )
            conn.commit()
        finally:
            conn.close()

        # Invalidate cache so the new record shows up immediately
        try:
            get_redis_connection().delete("employees_cache")
        except Exception as e:  # noqa: BLE001
            log.warning("Redis delete failed: %s", e)

        return redirect(url_for("index"))

    return render_template("add_employee.html")


@app.route("/delete/<int:emp_id>", methods=["POST"])
def delete_employee(emp_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        get_redis_connection().delete("employees_cache")
    except Exception as e:  # noqa: BLE001
        log.warning("Redis delete failed: %s", e)

    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Health endpoints - wire these up to Kubernetes probes
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    """Liveness probe - is the process itself alive?"""
    return jsonify(status="ok", pod=POD_NAME, version=APP_VERSION), 200


@app.route("/ready")
def ready():
    """Readiness probe - can we actually serve traffic (deps reachable)?"""
    status = {"mysql": "down", "redis": "down"}
    http_code = 200

    try:
        conn = get_mysql_connection(retries=1)
        conn.close()
        status["mysql"] = "up"
    except Exception:  # noqa: BLE001
        http_code = 503

    try:
        get_redis_connection().ping()
        status["redis"] = "up"
    except Exception:  # noqa: BLE001
        http_code = 503

    return jsonify(status), http_code


if __name__ == "__main__":
    # Give dependent services a moment on very first boot, then ensure schema exists.
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        log.error("Could not initialize DB on startup: %s", e)

    app.run(host="0.0.0.0", port=5000)
