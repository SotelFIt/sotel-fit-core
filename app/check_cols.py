from sqlalchemy import create_engine, text
DB = 'postgresql://postgres:UDTvvLDXJuMXNDvFGBKIOyEzCuqfCEmi@roundhouse.proxy.rlwy.net:25205/railway'
engine = create_engine(DB)
conn = engine.connect()
rows = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='clients' ORDER BY ordinal_position")).fetchall()
for r in rows:
    print(r[0])
conn.close()