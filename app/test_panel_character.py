"""Regression: enabling real materials while an overlapping drawer is open."""
import json
import os
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtWidgets import QApplication


@pytest.mark.skipif(not os.environ.get('BAILONG_TEST_MATERIALS'),reason='Requires locally downloaded verified materials')
def test_enable_materials_keeps_panel_above_character(qtbot,tmp_path,monkeypatch):
    data=tmp_path/'data';data.mkdir()
    (data/'material-preferences.json').write_text(json.dumps(dict(tier='hd',cardOnly=True)))
    monkeypatch.setenv('BAILONG_DATA_DIR',str(data))
    monkeypatch.setenv('BAILONG_HOME',str(tmp_path))
    monkeypatch.setattr(QApplication,'quit',lambda:None)
    from typography import install_ui_font
    install_ui_font(QApplication.instance())
    import storage_locations
    monkeypatch.setattr(storage_locations,'material_root',lambda state:Path(os.environ['BAILONG_TEST_MATERIALS']))
    from desktop import DesktopPet
    pet=DesktopPet(monitor=False);edge=pet._edge_controller
    qtbot.addWidget(pet);qtbot.addWidget(edge.window)
    try:
        assert pet._materials_missing and not pet.isVisible()
        edge.dock='right';edge.prefs['handle_position']=.49
        edge.open_original_settings();pet.settings_dialog.tabs.setCurrentIndex(3)
        edge.set_pinned(True);edge.reflow()
        assert pet.materials.request('hd')
        qtbot.waitUntil(lambda:pet.materials.job is None and not pet._materials_missing,timeout=30000)
        assert pet.isVisible() and pet.player is not None
        edge.reflow()
        stats=edge.window.nav['stats'];chat=edge.window.nav['chat']
        point=stats.mapToGlobal(stats.rect().center())
        pet.move(point-QPoint(pet.width()//2,pet.height()//2))
        pet.raise_()  # Same native reorder as revealing/activating the Tool window.
        qtbot.waitUntil(lambda:QApplication.widgetAt(point) is stats,timeout=2000)
        assert QApplication.widgetAt(chat.mapToGlobal(chat.rect().center())) is chat
        local=pet.mapFromGlobal(point)
        assert pet.panel_covers_point(local.x(),local.y())
        # Real character playback remains alive while panel navigation works.
        for key in ('stats','settings','overview'):
            qtbot.mouseClick(edge.window.nav[key],Qt.MouseButton.LeftButton)
            qtbot.wait(20);assert edge.current_page==key
        edge.window.hide()
        assert not pet.panel_covers_point(local.x(),local.y())
        assert pet.isVisible() and pet.tick.isActive()
    finally:
        edge.shutdown();pet.close()
