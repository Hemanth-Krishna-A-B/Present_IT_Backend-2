from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import pandas as pd
import os
from dotenv import load_dotenv
import tempfile

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-report")
def generate_report(session_id: int = Query(...)):
    try:
        response = supabase.rpc("get_session_report", {"session_id_input": session_id}).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase RPC error: {str(e)}")

    if not response.data:
        raise HTTPException(status_code=404, detail="No data found for this session")

    df = pd.DataFrame(response.data)
    csv_str = df.to_csv(index=False)

    filename = f"report_session_{session_id}.csv"
    file_path = f"reports/{filename}"

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=True) as temp_file:
        temp_file.write(csv_str)
        temp_file.flush()

        try:
            supabase.storage.from_("reports").upload(
                file_path,
                temp_file.name
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload to Supabase failed: {str(e)}")

    try:
        public_url = supabase.storage.from_("reports").get_public_url(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get public URL: {str(e)}")

    try:
        update_response = supabase.table("session").update({
            "report_url": public_url
        }).eq("id", session_id).execute()

        if not update_response.data:
            raise HTTPException(status_code=404, detail="No matching session found to update")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update session table: {str(e)}")

    try:
        supabase.table("poll-response").delete().eq("session_id", session_id).execute()
    except:
        print("error deleting poll_response table")
    try:
        supabase.table("attendance").delete().eq("session_id", session_id).execute()
    except:
        print("error deleting attendance table")
    try:
        supabase.table("leaderboard").delete().eq("session_id", session_id).execute()
    except:
        print("error deleting leaderboard table")

    return {
        "message": f"Report uploaded and session updated",
        "public_url": public_url,
        "rows": len(df)
    }
