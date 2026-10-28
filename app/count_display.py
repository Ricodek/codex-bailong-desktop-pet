"""One optical style for Chinese count units across labels, buttons and charts."""
import re
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QFont,QFontMetricsF,QPainter,QPalette,QTextLayout,QTextOption,QTextCharFormat
from PySide6.QtWidgets import QLabel,QPushButton,QStyle,QStyleOptionButton

COUNT=re.compile(r'[<>-]*\d+(?:\.\d+)?\u202f([十百千万亿京垓秭穰沟涧正载极]+)')


def count_fonts(font):
    number=QFont(font);number.setStyleName('');number.setWeight(QFont.Weight.Normal)
    unit=QFont(number)
    unit.setFamilies(['Microsoft YaHei UI','Microsoft YaHei','Noto Sans SC','sans-serif'])
    px=number.pixelSize()
    if px>0:unit.setPixelSize(min(px,max(12,round(px*.82))))
    return number,unit


def count_unit_rise(number,unit,text):
    """Align visible ink centers; CJK and Latin em baselines differ on Windows."""
    digit_box=QFontMetricsF(number).tightBoundingRect('0')
    unit_box=QFontMetricsF(unit).tightBoundingRect(text)
    return unit_box.center().y()-digit_box.center().y()


def draw_count_text(p,rect,text,font,alignment=Qt.AlignmentFlag.AlignLeft,wrap=False):
    """Shape normal-weight numbers and smaller units together on shared baselines."""
    if not COUNT.search(text):
        p.save();p.setFont(font);p.drawText(rect,alignment|Qt.AlignmentFlag.AlignVCenter,text);p.restore();return
    number,unit=count_fonts(font)
    p.save();p.setFont(number)
    layouts=[];height=0.
    for paragraph in text.split('\n'):
        layout=QTextLayout(paragraph,number,p.device())
        option=QTextOption();option.setAlignment(alignment&Qt.AlignmentFlag.AlignHorizontal_Mask)
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if wrap else QTextOption.WrapMode.NoWrap)
        layout.setTextOption(option)
        formats=[]
        for match in COUNT.finditer(paragraph):
            span=QTextLayout.FormatRange();span.start=len(paragraph[:match.start(1)].encode('utf-16-le'))//2;span.length=len(match[1])
            span.format=QTextCharFormat();span.format.setFont(unit)
            rise=count_unit_rise(number,unit,match[1])
            span.format.setBaselineOffset(100*rise/max(1.,QFontMetricsF(unit).height()))
            formats.append(span)
        layout.setFormats(formats);layout.beginLayout();local_height=0.
        while True:
            line=layout.createLine()
            if not line.isValid():break
            line.setLineWidth(max(1.,rect.width()));line.setPosition(QPointF(0,local_height));local_height+=line.height()
        layout.endLayout();layouts.append((layout,height));height+=local_height
    offset=(rect.height()-height)/2 if alignment&Qt.AlignmentFlag.AlignVCenter else rect.height()-height if alignment&Qt.AlignmentFlag.AlignBottom else 0.
    for layout,y in layouts:layout.draw(p,QPointF(rect.left(),rect.top()+offset+y))
    p.restore()


class CountLabel(QLabel):
    def paintEvent(self,event):
        if not COUNT.search(self.text()) or self.textFormat()==Qt.TextFormat.RichText:
            return super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        rect=QRectF(self.contentsRect()).adjusted(self.margin(),self.margin(),-self.margin(),-self.margin())
        draw_count_text(p,rect,self.text(),self.font(),self.alignment(),self.wordWrap());p.end()


class CountButton(QPushButton):
    def paintEvent(self,event):
        if not COUNT.search(self.text()):return super().paintEvent(event)
        option=QStyleOptionButton();self.initStyleOption(option);option.text=''
        p=QPainter(self);self.style().drawControl(QStyle.ControlElement.CE_PushButton,option,p,self)
        p.setPen(option.palette.color(QPalette.ColorRole.ButtonText))
        rect=QRectF(self.style().subElementRect(QStyle.SubElement.SE_PushButtonContents,option,self))
        draw_count_text(p,rect,self.text(),self.font(),Qt.AlignmentFlag.AlignCenter);p.end()
