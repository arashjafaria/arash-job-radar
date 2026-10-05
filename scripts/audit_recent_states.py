"""Read-only diagnostic of recent job states. Never writes Supabase or Telegram."""
import os
from collections import Counter
import requests

url=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/arash_jobs"
key=os.environ["SUPABASE_SECRET_KEY"]
headers={"apikey":key,"Authorization":"Bearer "+key}
r=requests.get(url,headers=headers,params={
    "select":"id,source,job_id,title,company,location,posted_at,match_score,status,sent_to_telegram",
    "order":"id.desc","limit":"500"
},timeout=30)
r.raise_for_status()
rows=r.json()
print("AUDIT rows:",len(rows))
for source in ("linkedin","bmw","stepstone","indeed"):
    src=[x for x in rows if x.get("source")==source]
    print("\nSOURCE",source,"rows",len(src))
    for status,count in Counter((x.get("status") or "") for x in src).most_common():
        print(" STATUS",status,count)
    print(" SENT",sum(bool(x.get("sent_to_telegram")) for x in src))
print("\nRECENT LINKEDIN (latest database rows)")
for x in [r for r in rows if r.get("source")=="linkedin"][:40]:
    print("ROW",x.get("id"),"|",x.get("job_id"),"|",x.get("status"),"| score",x.get("match_score"),"|",x.get("posted_at"),"|",x.get("title"))
print("\nTARGETED TITLES")
for x in rows:
    title=(x.get("title") or "").lower()
    if "canoe" in title or "system architect" in title or "test automation" in title:
        print("TARGET",x.get("id"),"|",x.get("source"),"|",x.get("job_id"),"|",x.get("status"),"| score",x.get("match_score"),"|",x.get("posted_at"),"|",x.get("title"))
