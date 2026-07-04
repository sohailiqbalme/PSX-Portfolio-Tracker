import re

with open('app/api/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove auth imports
content = re.sub(r'^from app\.auth import require_auth, get_current_user_id\n', '', content, flags=re.MULTILINE)

# 2. Update _LAST_SYNC_TIMES comment and usage
content = content.replace('Maps user_id -> datetime of last successful sync', 'Maps "global" -> datetime of last successful sync')
content = content.replace('last_sync = _LAST_SYNC_TIMES.get(user_id)', 'last_sync = _LAST_SYNC_TIMES.get("global")')
content = content.replace('_LAST_SYNC_TIMES[user_id] = datetime.now()', '_LAST_SYNC_TIMES["global"] = datetime.now()')

# 3. Remove all @require_auth decorators
content = re.sub(r'^\s*@require_auth\n', '', content, flags=re.MULTILINE)

# 4. Remove all user_id = get_current_user_id() lines
content = re.sub(r'^\s*user_id\s*=\s*get_current_user_id\(\)\n', '', content, flags=re.MULTILINE)

# 5. Remove any query filters for user_id
content = re.sub(r'\s*\.filter\(Portfolio\.user_id == user_id\)', '', content)

# 6. Remove 'if portfolio.user_id != user_id:' checks and their returns
content = re.sub(r'^\s*if portfolio\.user_id != user_id:\n\s*return _error\(\"Unauthorized.*?\n', '', content, flags=re.MULTILINE)

# 7. Remove user_id from portfolio creation
content = re.sub(r'\s*user_id=user_id,', '', content)

# 8. Clean up logging references to user_id
content = content.replace('user=%s ', '')
content = content.replace('user_id, ', '')
content = content.replace(' | user=%s', '')

# 9. Handle GET /api/v1/portfolios Default Portfolio logic
# We inject auto-seed logic when fetching portfolios
auto_seed_logic = """
    portfolios = db.session.query(Portfolio).all()
    
    if not portfolios:
        # Auto-seed default portfolio
        default_portfolio = Portfolio(
            name="Default Portfolio",
            initial_balance=1000000.0,
            description="Primary trading ledger"
        )
        db.session.add(default_portfolio)
        db.session.commit()
        portfolios = [default_portfolio]
        logger.info("Auto-seeded Default Portfolio (id=%s)", default_portfolio.id)
"""
content = re.sub(
    r'\s*portfolios = \(\n\s*db\.session\.query\(Portfolio\)\n\s*\.all\(\)\n\s*\)',
    auto_seed_logic,
    content
)

# For sync-live route specifically, there was another query block for portfolios:
#         portfolios = (
#            db.session.query(Portfolio)
#            .all()
#        )
sync_seed = """
        portfolios = db.session.query(Portfolio).all()
"""
content = re.sub(
    r'\s*portfolios = \(\n\s*db\.session\.query\(Portfolio\)\n\s*\.all\(\)\n\s*\)',
    sync_seed,
    content
)

with open('app/api/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced auth in routes.py')
