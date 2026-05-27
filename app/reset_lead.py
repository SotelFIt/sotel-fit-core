from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:UDTvvLDXJuMXNDvFGBKIOyEzCuqfCEmi@roundhouse.proxy.rlwy.net:25205/railway')
conn = engine.connect()
conn.execute(text("UPDATE conversation_states SET step='start', status='lead' WHERE phone='+5517991089991'"))
conn.commit()
print('Reset feito')
conn.close()