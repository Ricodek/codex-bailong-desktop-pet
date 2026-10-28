"""Chinese count boundaries and the actual visible checkbox indicator."""
import pytest
import re
from token_calendar import compact_tokens


@pytest.mark.parametrize('value,expected', [
    (0,'0'), (99,'99'), (100,'1百'), (217,'2.17百'), (999,'9.99百'),
    (1000,'1千'), (10000,'1万'), (100000,'1十万'), (1000000,'1百万'),
    (10000000,'1千万'), (100000000,'1亿'), (217280000,'2.17亿'),
    (10**9,'1十亿'), (10**10,'1百亿'), (10**11,'1千亿'),
    (10**12,'1万亿'), (10**13,'1十万亿'), (10**14,'1百万亿'),
    (10**15,'1千万亿'), (10**16,'1京'), (10**20,'1垓'),
    (10**48,'1极'), (10**400,'>9999极'), (999999,'1百万'), (999499,'9.99十万'),
    (99999999,'1亿'), (999999999999,'1万亿'), (-217280000,'-2.17亿'),
])
def test_chinese_counts(value,expected):
    assert compact_tokens(value)==re.sub(r'(?<=\d)(?=[\u4e00-\u9fff])','\u202f',expected)


def test_checkbox_visible_tick_and_native_input(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyle,QStyleOptionButton
    from PySide6.QtGui import QColor
    from settings_controls import MarkedCheckBox
    w=MarkedCheckBox('减少动态效果');w.resize(280,40)
    qtbot.addWidget(w);w.show();w.clearFocus();qtbot.wait(20)
    option=QStyleOptionButton();w.initStyleOption(option)
    rect=w.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator,option,w)
    def white_mark_pixels():
        image=w.grab().toImage();scale=w.devicePixelRatioF()
        area=rect.adjusted(4,4,-4,-4)
        return sum(image.pixelColor(round(x*scale),round(y*scale))==QColor('#ffffff')
                   for x in range(area.left(),area.right()+1)
                   for y in range(area.top(),area.bottom()+1))
    assert not w.isChecked() and white_mark_pixels()==0
    qtbot.mouseClick(w,Qt.MouseButton.LeftButton,pos=rect.center());qtbot.wait(10)
    assert w.isChecked() and white_mark_pixels()>2
    qtbot.keyClick(w,Qt.Key.Key_Space)
    assert not w.isChecked()
    w.setEnabled(False);qtbot.mouseClick(w,Qt.MouseButton.LeftButton,pos=rect.center())
    assert not w.isChecked()


def test_global_count_rendering_keeps_plain_accessible_text(qtbot):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QWidget,QVBoxLayout
    from count_display import CountLabel,CountButton,count_fonts
    host=QWidget();layout=QVBoxLayout(host)
    for text in ('2.17\u202f亿 Token','9.87\u202f千万','1\u202f万亿','模型\n3.2\u202f百万 Token  50%'):
        for kind in (CountLabel,CountButton):
            widget=kind(text);font=QFont('Segoe UI');font.setPixelSize(24);font.setBold(True)
            widget.setFont(font);layout.addWidget(widget)
            assert widget.text()==text
    qtbot.addWidget(host);host.resize(420,390);host.show();qtbot.wait(20)
    assert not host.grab().isNull()
    number,unit=count_fonts(font)
    assert number.weight()==unit.weight()==QFont.Weight.Normal
    assert unit.pixelSize()==20<number.pixelSize()
