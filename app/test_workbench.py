import math
import os
import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QPoint,QRect
from PySide6.QtWidgets import QApplication
from dock_motion import Spring


def test_spring_reversal_and_frame_independence():
    a=Spring(0);b=Spring(0);a.target=b.target=1
    for _ in range(30):a.advance(1/60)
    for _ in range(60):b.advance(1/120)
    assert abs(a.value-b.value)<1e-10
    before=a.value;velocity=a.velocity;a.target=0
    assert a.value==before and a.velocity==velocity
    for _ in range(120):a.advance(1/60)
    assert a.settled and a.value==0


def test_source_panel_clicks_drag_and_all_edges(qtbot,tmp_path,monkeypatch):
    # Paths are fixed before importing application globals.
    monkeypatch.setenv('BAILONG_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('BAILONG_HOME',str(tmp_path))
    monkeypatch.setattr(QApplication,'quit',lambda:None)
    from desktop import DesktopPet
    import workbench_panel
    monkeypatch.setattr(workbench_panel,'CONFIG',tmp_path/'panel.json')
    pet=DesktopPet(monitor=False);edge=pet._edge_controller
    qtbot.addWidget(pet);qtbot.addWidget(edge.window)
    edge.timer.stop();edge.set_pinned(True)
    qtbot.wait(30)
    try:
        pet.bubble.token_snapshot=None
        for _ in range(3):
            for name in ('stats','settings','overview'):
                started=time.perf_counter()
                qtbot.mouseClick(edge.window.nav[name],Qt.MouseButton.LeftButton)
                qtbot.wait(10)
                assert edge.current_page==name
                assert time.perf_counter()-started<1
        assert pet.bubble.report is None  # No hidden legacy report construction.
        edge.statistics.select_mode('models')
        assert edge.statistics.total.text()=='— Token'
        pet.bubble.token_snapshot=dict(today='2026-10-28',report=dict(day='2026-10-27',daily_models=[
            dict(day='2026-10-28',model='test',total=30,input=20,output=10,known=True)]))
        edge.statistics.select_mode('models')
        assert edge.statistics.chart.series['total']==30
        edge.statistics.select_mode('quota');edge.statistics.select_mode('usage')
        edge.statistics.chart.set_series(dict(mode='bars',available=True,bins=[dict(value=72230000)]))
        from PySide6.QtGui import QFontMetrics
        assert edge.statistics.chart.plot_rect().left()>QFontMetrics(workbench_panel.ui_font(16)).horizontalAdvance(workbench_panel.compact(72230000))
        edge.open_original_settings();qtbot.wait(30)
        assert edge.current_page=='original_settings'
        assert edge.window.height()<=700
        for i in range(6):
            pet.settings_dialog.tabs.setCurrentIndex(i);qtbot.wait(20)
            assert i in pet.settings_dialog._built_pages
        edge.navigate('overview');qtbot.wait(20)
        assert edge.window.height()<500
        for scale in (1.,1.1):
            edge.set_preference('panel_scale',scale)
            assert edge.overview.tokens.isVisible()
        edge.set_preference('panel_scale',1.)
        # Header mouse path must move the actual native panel without the pet.
        old_pet=pet.pos();old=edge.window.pos();header=edge.window.header
        qtbot.mousePress(header,Qt.MouseButton.LeftButton,pos=QPoint(90,15))
        qtbot.mouseMove(header,QPoint(120,35));qtbot.mouseRelease(header,Qt.MouseButton.LeftButton,pos=QPoint(120,35))
        assert edge.window.pos()!=old and pet.pos()==old_pet
        area=edge.screen().availableGeometry()
        edge.window.move(area.right()-edge.window.width()+90,area.top()+100)
        edge.finish_drag()
        assert edge.dock=='right'  # Crossing beyond the edge must still dock.
        edge.animation.stop()
        for dock in ('left','right','top','bottom'):
            edge.dock=dock;edge.prefs['handle_position']=.35
            edge.reflow();edge.set_preference('reduced_motion',True)
            edge.collapse();assert not edge.window.isVisible()
            edge._dismissed=False
            point=edge.hot_rect.center()
            edge.tick(point,now=10);edge.tick(point,now=11)
            assert edge.window.isVisible() and edge.progress==1
            edge.tick(QPoint(area.center().x(),area.bottom()-20),now=12)
            edge.tick(QPoint(area.center().x(),area.bottom()-20),now=14)
        edge.dock=None;edge.set_pinned(False);edge.expand()
        edge.tick(QPoint(-2000,-2000),now=20);edge.tick(QPoint(-2000,-2000),now=22)
        assert edge.window.isVisible()  # Floating panels stay where placed.
        class LeftMonitor:
            def availableGeometry(self):return QRect(-1920,-120,1920,1080)
            def name(self):return 'negative-test'
        monkeypatch.setattr(edge,'screen',lambda:LeftMonitor())
        for dock in ('left','right','top','bottom',None):
            edge.dock=dock;edge.prefs['position']=[-1500,100];edge.reflow()
            assert LeftMonitor().availableGeometry().contains(edge.open_rect)
    finally:
        edge.shutdown();pet.close()
