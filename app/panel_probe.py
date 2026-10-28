"""Local native-input acceptance session. Never sends chat or fetches credentials."""
import json,time,sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QObject,QEvent


def run(folder):
    dest=Path(folder);dest.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from typography import install_ui_font
    install_ui_font(app)
    from desktop import DesktopPet
    pet=DesktopPet(monitor=False);edge=pet._edge_controller
    class InputTrace(QObject):
        def eventFilter(self,obj,event):
            if event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease):
                with (dest/'input.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(dict(event=event.type().name,target=type(obj).__name__,
                        name=obj.objectName(),window=obj.window().windowTitle() if hasattr(obj,'window') else '',
                        grabber=type(QWidget.mouseGrabber()).__name__),ensure_ascii=False)+'\n')
            return False
    from PySide6.QtWidgets import QWidget
    trace=InputTrace();app.installEventFilter(trace)
    gaps=[];last=[time.perf_counter()];seen=set()
    clock=QTimer();clock.setInterval(20)
    def beat():
        now=time.perf_counter();gaps.append((now-last[0])*1000);last[0]=now
    clock.timeout.connect(beat);clock.start()
    record=QTimer();record.setInterval(500)
    def save():
        commands=dest/'command.json'
        if commands.exists():
            command=json.loads(commands.read_text(encoding='utf-8'));commands.unlink()
            if command.get('action')=='pin':edge.set_pinned(True);edge.reflow()
            elif command.get('action')=='floating':edge.dock=None;edge.reflow();edge.expand()
        data=dict(page=edge.current_page,dock=edge.dock,progress=edge.progress,
                  open=edge.window.isVisible(),bounds=list(edge.window.geometry().getRect()),
                  hot_rect=list(edge.hot_rect.getRect()),animation_active=edge.animation.isActive(),
                  font=edge.prefs['font_size'],scale=edge.prefs['panel_scale'],
                  dpr=edge.window.devicePixelRatioF(),heartbeat_max_ms=max(gaps,default=0),
                  heartbeat_samples=len(gaps),data_dir=str(__import__('app_paths').data_dir()))
        data['widgets']=[dict(kind=type(w).__name__,title=w.windowTitle(),visible=w.isVisible(),
            enabled=w.isEnabled(),bounds=list(w.geometry().getRect()),flags=int(w.windowFlags())) for w in app.topLevelWidgets()]
        data['mouse_grabber']=type(QWidget.mouseGrabber()).__name__
        data['active_modal']=type(app.activeModalWidget()).__name__
        data['active_popup']=type(app.activePopupWidget()).__name__
        data['pid']=__import__('os').getpid()
        data['active_window']=type(app.activeWindow()).__name__
        data['nav_hits']={}
        for key,button in edge.window.nav.items():
            point=button.mapToGlobal(button.rect().center());hit=app.widgetAt(point)
            data['nav_hits'][key]=dict(point=[point.x(),point.y()],kind=type(hit).__name__,
                name=hit.objectName() if hit else '',window=hit.window().windowTitle() if hit else '')
        (dest/'status.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        key=(edge.current_page,edge.dock,round(edge.progress))
        if edge.window.isVisible() and edge.progress==1 and key not in seen:
            seen.add(key);edge.window.grab().save(str(dest/(edge.current_page+'.png')))
    record.timeout.connect(save);record.start()
    if '--probe-hot-material' in sys.argv:
        def prepare_material():
            edge.open_original_settings();pet.settings_dialog.tabs.setCurrentIndex(3)
            edge.set_pinned(True)
            QTimer.singleShot(1000,lambda:pet.materials.request('hd'))
            QTimer.singleShot(2500,edge.reflow)
        QTimer.singleShot(250,prepare_material)
    control=QTimer();control.setInterval(250)
    control.timeout.connect(lambda:pet.close() if (dest/'quit').exists() else None);control.start()
    QTimer.singleShot(300000,pet.close)
    edge.expand()
    return app.exec()
