path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/main.py'
content = open(path, 'r', encoding='utf-8-sig').read()

old = "app.include_router(stripe_checkout_router)"
new = """app.include_router(stripe_checkout_router)
try:
    from routers.body_analysis import router as body_analysis_router
    app.include_router(body_analysis_router)
    logger.info("Body analysis router carregado")
except Exception as e:
    logger.error(f"Body analysis router nao carregado: {e}")"""

content = content.replace(old, new, 1)
open(path, 'w', encoding='utf-8').write(content)
print('OK')