from fastapi import FastAPI
import duckdb
import time
import threading

app = FastAPI()

# ============================================================
#  SINGLE PERSISTENT CONNECTION  (file kabhi band nahi hogi)
# ============================================================
con = duckdb.connect(database=':memory:', read_only=False)

# Cache ON — metadata ek baar load, phir RAM me
con.execute("SET enable_http_metadata_cache=true")
con.execute("SET enable_object_cache=true")
con.execute("SET threads=4")

# Lock — DuckDB ek time pe ek query (thread-safe)
db_lock = threading.Lock()

# Naya single-file repo (screenshot wala)
FILE_URL = "hf://datasets/HiTeckGroup/HiTeckNumInfo/users_data.parquet"

# Column name jo naye file me hai (screenshot error se pata chala)
PHONE_COLUMN = "mobile"


# ============================================================
#  STARTUP — file pehle hi open ho jaye
# ============================================================
@app.on_event("startup")
def warm_up_file():
    try:
        with db_lock:
            con.execute(
                f"SELECT 1 FROM read_parquet('{FILE_URL}') LIMIT 1"
            ).fetchone()
        print(f"✅ File opened & cached: {FILE_URL}")
    except Exception as e:
        print(f"⚠️ Warm-up error: {e}")


# ============================================================
#  SEARCH FUNCTION — poora wait karega, jab tak result na mile
#  ya confirm ho jaye ki number nahi hai
# ============================================================
def search_number(target_num: str):
    query = f"SELECT * FROM read_parquet(?) WHERE {PHONE_COLUMN} = ? LIMIT 1"
    with db_lock:
        result = con.execute(query, [FILE_URL, target_num]).df()
    return result if not result.empty else None


# ============================================================
#  API ROUTE
# ============================================================
@app.get("/api/num/input={target_number}")
def public_search(target_number: str):
    start_time = time.time()

    try:
        final_result = search_number(target_number)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Search error: {str(e)}",
            "time_taken": f"{time.time() - start_time:.2f}s"
        }

    end_time = time.time()
    time_taken = f"{end_time - start_time:.2f}s"

    # ✅ Result mila to hi response dega
    if final_result is not None and not final_result.empty:
        return {
            "status": "success",
            "time_taken": time_taken,
            "registered": True,
            "data": final_result.to_dict(orient="records")[0]
        }

    # ❌ Jab tak pura search complete ho jaye aur kuch na mile, tab hi ye aayega
    return {
        "status": "not_found",
        "registered": False,
        "message": "Ye number database me nahi mila",
        "time_taken": time_taken
    }


@app.get("/")
def home():
    return {
        "status": "Ultra-Fast Public OSINT API is Live! 🔥",
        "usage": "/api/num/input={number}"
    }
