from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:UDTvvLDXJuMXNDvFGBKIOyEzCuqfCEmi@roundhouse.proxy.rlwy.net:25205/railway')
conn = engine.connect()
rows = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")).fetchall()
for r in rows:
    print(r[0])
conn.close()