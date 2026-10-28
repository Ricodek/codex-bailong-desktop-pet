"""Optional startup without creating shortcuts or scripts in the C profile."""
KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'


def read(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY) as key:
            return winreg.QueryValueEx(key,name)[0]
    except FileNotFoundError:return None


def write(name,value):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as key:
        if value is None:
            try:winreg.DeleteValue(key,name)
            except FileNotFoundError:pass
        else:winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
