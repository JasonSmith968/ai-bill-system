import re


def validate_password_strength(password):
    """验证密码强度。返回 (is_valid, error_message)。"""
    if not password:
        return False, '密码不能为空'
    if len(password) < 8:
        return False, '密码长度不能少于8位'
    if len(password) > 128:
        return False, '密码长度不能超过128位'
    if not re.search(r'[A-Za-z]', password):
        return False, '密码必须包含字母'
    if not re.search(r'[0-9]', password):
        return False, '密码必须包含数字'
    return True, ''


def parse_user_agent(user_agent_string):
    """轻量级 User-Agent 解析，返回 {device_type, browser, os}。"""
    ua = user_agent_string or ''
    ua_lower = ua.lower()

    device_type = 'desktop'
    if any(k in ua_lower for k in ['mobile', 'android', 'iphone', 'ipad']):
        device_type = 'mobile' if 'ipad' not in ua_lower else 'tablet'

    browser = 'Unknown'
    if 'Edg/' in ua or 'Edge/' in ua:
        browser = 'Edge'
    elif 'Chrome' in ua and 'Chromium' not in ua:
        browser = 'Chrome'
    elif 'Firefox' in ua:
        browser = 'Firefox'
    elif 'Safari' in ua and 'Chrome' not in ua:
        browser = 'Safari'

    os_name = 'Unknown'
    if 'Windows' in ua:
        os_name = 'Windows'
    elif 'Mac OS' in ua or 'Macintosh' in ua:
        os_name = 'macOS'
    elif 'Linux' in ua and 'Android' not in ua:
        os_name = 'Linux'
    elif 'Android' in ua:
        os_name = 'Android'
    elif 'iOS' in ua or 'iPhone' in ua or 'iPad' in ua:
        os_name = 'iOS'

    return {
        'device_type': device_type,
        'browser': browser,
        'os': os_name
    }
