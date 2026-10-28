"""Native, compact edge drawer. The original character and data engine remain intact."""
from pathlib import Path
from version import VERSION
import json
import math
import os
import re
import sys
import time

from PySide6.QtCore import (Qt, QObject, QTimer, QRect, QRectF, QPoint, QPointF,
                            QSize, Signal, QVariantAnimation, QEasingCurve, QEvent)
from PySide6.QtGui import (QColor, QPainter, QPen, QPainterPath, QFont,
                           QFontMetrics, QCursor)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QToolButton,
    QPushButton, QVBoxLayout, QHBoxLayout, QStackedWidget, QScrollArea,
    QSizePolicy, QComboBox, QCheckBox, QAbstractButton, QLineEdit,
    QPlainTextEdit, QTextEdit, QTabBar, QFrame)
from PySide6.QtWidgets import QLayout

LAYOUT_ID='workbench-1.3'
BASE=Path(__file__).resolve().parent
from app_paths import data_dir
from count_display import CountLabel,CountButton,draw_count_text
CONFIG=data_dir()/'panel-display.json'
DEFAULTS={'schema':2,'panel_scale':1.0,'font_size':17,'edge':'right',
          'hover_ms':180,'hide_ms':450,'handle_position':0.48,'reduced_motion':False,'dock':None,'position':None,'screen':None}
INK='#38333f'
MUTED='#776f80'
ACCENT='#7b6596'
LINE='#e7e1ec'
SURFACE='#fbfafc'
FONT_BASE=17
_installed=False
_controllers=[]

def preferences():
    result=dict(DEFAULTS)
    try:
        saved=json.loads(CONFIG.read_text(encoding='utf-8'))
        if saved.get('schema',0)>=2:
            for key in result:
                if key in saved:
                    result[key]=saved[key]
    except (OSError,ValueError,TypeError):
        pass
    if result['panel_scale'] not in (1.0,1.1):result['panel_scale']=1.0
    if result['font_size'] not in (16,17,18,19):result['font_size']=17
    if result['edge'] not in ('left','right'):result['edge']='right'
    result['hide_ms']=max(250,min(1500,int(result['hide_ms'])))
    result['hover_ms']=max(100,min(600,int(result['hover_ms'])))
    result['handle_position']=max(0.,min(1.,float(result['handle_position'])))
    return result

def save_preferences(values):
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    temporary=CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,CONFIG)

def ui_font(px=17,bold=False):
    font=QFont()
    font.setFamilies(['Segoe UI','Microsoft YaHei UI','Noto Sans SC','sans-serif'])
    sizes=(FONT_BASE-1,FONT_BASE,FONT_BASE+3,FONT_BASE+7)
    font.setPixelSize(min(sizes,key=lambda n:abs(n-px)))
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font

def label(text='',size=17,bold=False,parent=None):
    widget=CountLabel(text,parent)
    widget.setFont(ui_font(size,bold))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget

def line():
    frame=QFrame()
    frame.setFrameShape(QFrame.Shape.HLine)
    frame.setFixedHeight(1)
    frame.setStyleSheet('background:'+LINE+';border:0;')
    return frame

def button(text,name='',callback=None,quiet=False):
    widget=CountButton(text) if '\u202f' in text else QPushButton(text)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.setMinimumHeight(34)
    widget.setProperty('quiet',quiet)
    if callback is not None:widget.clicked.connect(callback)
    return widget

def clear_layout(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():clear_layout(item.layout())

def compact(value):
    from token_calendar import compact_tokens
    return compact_tokens(int(value or 0))


def enrich_editor(root,body_size=17):
    """Enlarge text and reflow native layouts; never scale a screenshot or the pet."""
    minimum=max(15,body_size-1)
    def replace_size(match):
        number=float(match.group(1))
        return 'font-size:'+str(min((body_size-1,body_size,body_size+3,body_size+7),key=lambda n:abs(n-number)))+'px'
    for widget in [root]+root.findChildren(QWidget):
        if not widget.property('edgeOriginalStyle'):
            widget.setProperty('edgeOriginalStyle',widget.styleSheet() or ' ')
        stylesheet=widget.property('edgeOriginalStyle').strip()
        if stylesheet:
            adapted=re.sub(r'font-size\s*:\s*([\d.]+)px',replace_size,stylesheet)
            if widget.styleSheet()!=adapted:widget.setStyleSheet(adapted)
        font=ui_font(body_size)
        widget.setFont(font)
        if isinstance(widget,QLabel):
            if widget.textFormat()!=Qt.TextFormat.PlainText and 'font-size:' in widget.text():
                widget.setText(re.sub(r'font-size\s*:\s*([\d.]+)px',replace_size,widget.text()))
            widget.setMinimumWidth(0)
        if isinstance(widget,(QAbstractButton,QComboBox,QLineEdit)):
            if 0<widget.maximumHeight()<34:widget.setFixedHeight(34)
            else:widget.setMinimumHeight(max(widget.minimumHeight(),32))
        if type(widget) is QWidget and widget.minimumHeight()==widget.maximumHeight() and 18<=widget.maximumHeight()<=30:
            widget.setFixedHeight(36)
        if isinstance(widget,QTabBar):
            widget.setExpanding(False)
            widget.setUsesScrollButtons(True)
        widget.updateGeometry()
    root.updateGeometry()

def adapt_settings(widget,body_size):
    enrich_editor(widget,body_size)
    if hasattr(widget,'tabs'):widget.tabs.setTabText(0,'常规')
    for text_widget in widget.findChildren(QLabel):
        if any(text in text_widget.text() for text in ('卡片与快捷入口','自动模式闲置后收起','仅卡片','胶囊')):
            text_widget.hide()
    forms=getattr(widget,'_page_forms',{})
    forms=forms.values() if isinstance(forms,dict) else forms
    fields=getattr(widget,'fields',{})
    for form in forms:
        if hasattr(form,'setFormAlignment'):form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    from settings_controls import SwitchRow
    for field in widget.findChildren(SwitchRow):
        field.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        field.setFixedHeight(field.heightForWidth(max(240,widget.width()-50)))
    for name in ('panel_detached','bubble','bubble_mode','quota_visible','capsule_action','capsule_website'):
        field=fields.get(name)
        if not field:continue
        field.hide()
        for form in forms:
            if hasattr(form,'labelForField'):
                associated=form.labelForField(field)
                if associated:associated.hide()
            if hasattr(form,'setRowVisible') and form.indexOf(field)>=0:
                form.setRowVisible(field,False)

class QuotaRows(QWidget):
    activated=Signal()
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.items=[]
        self.setObjectName('edge_quota_rows')
        self.setFixedHeight(124)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.expired=set()

    def refresh(self):
        from quota_summary_data import quota_items
        bubble=self.controller.bubble
        self.items=quota_items(bubble.windows)
        self.setAccessibleName('\n'.join(str(item.get('description','')) for item in self.items))
        for item in self.items:
            key=(item.get('id'),item.get('reset_at'))
            if item.get('expired') and key not in self.expired:
                self.expired.add(key)
                QTimer.singleShot(0,bubble.quotaRefreshRequested.emit)
        self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body=self.controller.prefs['font_size']
        items=self.items or [{'label':'账户额度','display':'—','reset_text':'正在读取额度','progress':None}]
        for i,item in enumerate(items[:2]):
            top=3+i*63
            name=str(item.get('label','额度')).replace('5h剩余','5小时').replace('周剩余','一周').replace('剩余','')
            p.setFont(ui_font(body))
            p.setPen(QColor(INK))
            caption=name if name.endswith('额度') else name+'额度'
            p.drawText(QRectF(0,top,self.width()-100,28),Qt.AlignmentFlag.AlignVCenter,caption+'  ›')
            p.setFont(ui_font(body+7,True))
            p.drawText(QRectF(self.width()-112,top-1,112,30),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,str(item.get('display','—')))
            p.setFont(ui_font(body-1))
            p.setPen(QColor(MUTED))
            text=str(item.get('reset_text','重置时间未知'))
            text=QFontMetrics(p.font()).elidedText(text,Qt.TextElideMode.ElideRight,max(80,self.width()-140))
            p.drawText(QRectF(0,top+29,self.width()-136,23),Qt.AlignmentFlag.AlignVCenter,text)
            track=QRectF(self.width()-118,top+38,118,4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#e5deec'))
            p.drawRoundedRect(track,2,2)
            progress=item.get('progress')
            if progress is not None:
                p.setBrush(QColor('#a56880' if item.get('low') else ACCENT if i==0 else '#8b82a2'))
                p.drawRoundedRect(QRectF(track.left(),track.top(),track.width()*max(0,min(1,float(progress))),4),2,2)
        p.end()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.activated.emit()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Space):self.activated.emit()
        else:super().keyPressEvent(event)

class TokenRow(QAbstractButton):
    def __init__(self,controller):
        super().__init__();self.controller=controller;self.value='—'
        self.setObjectName('edge_today_tokens');self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('今日 Token，打开今日每小时用量')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse() or self.hasFocus():
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#f1ebf6'));p.drawRoundedRect(QRectF(self.rect()),6,6)
        size=self.controller.prefs['font_size'];p.setPen(QColor(INK));p.setFont(ui_font(size))
        p.drawText(QRectF(0,0,self.width()-140,self.height()),Qt.AlignmentFlag.AlignVCenter,'今日 Token')
        p.setFont(ui_font(size+6,True))
        draw_count_text(p,QRectF(self.width()-145,0,123,self.height()),self.value,p.font(),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        p.setPen(QColor(MUTED));p.setFont(ui_font(20))
        p.drawText(QRectF(self.width()-14,0,14,self.height()),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,'›')
        p.end()

class Overview(QWidget):
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(11)
        self.session=button('Codex', 'edge_session',self.open_session,True)
        self.session.setMinimumHeight(54)
        self.session.setMaximumHeight(64)
        self.session.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.session.setStyleSheet('QPushButton{text-align:left;padding:0;border:0;background:transparent;}QPushButton:hover{color:'+ACCENT+';}')
        layout.addWidget(self.session)
        layout.addWidget(line())
        self.quotas=QuotaRows(controller)
        self.quotas.activated.connect(lambda:controller.navigate('details'))
        layout.addWidget(self.quotas)
        layout.addWidget(line())
        self.tokens=TokenRow(controller)
        self.tokens.clicked.connect(lambda:controller.show_tokens('day'))
        layout.addWidget(self.tokens)
        self.note=label('完整状态与重置说明  ›',15)
        self.note.setStyleSheet('color:'+MUTED+';')
        self.note.setCursor(Qt.CursorShape.PointingHandCursor)
        self.note.mouseReleaseEvent=lambda event:controller.navigate('details')
        layout.addWidget(self.note)
        layout.removeWidget(self.note);self.note.hide()
        self.quotas.setToolTip('点击查看完整状态、额度与重置说明')
        layout.addStretch(1)
        self.current_id=''

    def refresh(self):
        b=self.controller.bubble
        from conversation_roster import LABELS
        selected,extra=b.roster.selection(b.status_indicator.unread)
        if selected:
            row=selected[0]
            title=str(row.get('title') or row.get('name') or 'Codex')
            self.current_id=str(row.get('id') or row.get('conversation_id') or '')
            state=LABELS.get(row.get('state'),str(row.get('state') or '进行中'))
            if extra or len(selected)>1:state+='  ·  '+str(len(selected)+extra)+' 个会话'
        else:
            title='当前状态'
            state=str(b.status or '暂无进行中的任务').replace('\n',' ')
            self.current_id=''
        metrics=QFontMetrics(ui_font(self.controller.prefs['font_size']))
        width=max(120,self.width()-4)
        title=metrics.elidedText(title,Qt.TextElideMode.ElideRight,width)
        state=metrics.elidedText(state,Qt.TextElideMode.ElideRight,width)
        self.session.setText(title+'\n'+state)
        self.session.setToolTip(str(b.status))
        self.quotas.refresh()
        from quota_summary_data import today_tokens
        today=today_tokens(b.token_snapshot)
        self.tokens.value=str(today.get('display','—'));self.tokens.update()
        self.tokens.setToolTip(str(today.get('description','今日 Token')))

    def open_session(self):
        if self.current_id:self.controller.bubble.conversationRequested.emit(self.current_id)
        else:self.controller.bubble.codexRequested.emit()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        QTimer.singleShot(0,self.refresh)

class SeriesChart(QWidget):
    hoverText=Signal(str)
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.series={}
        self.hover=-1
        self.setMouseTracking(True)
        self.setMinimumHeight(180)
        self.setAccessibleName('Token 用量图')

    def set_series(self,series):
        self.series=series
        self.hover=-1
        self.setAccessibleDescription(str(series.get('title',''))+'，总量 '+str(series.get('total',0))+' Token')
        self.update()

    def plot_rect(self):
        high=max(1,max((float(b.get('value') or 0) for b in self.series.get('bins',[]) if not b.get('future')),default=0))
        metrics=QFontMetrics(ui_font(self.controller.prefs['font_size']-1))
        captions=[compact(high*f) if high>=100 else format(high*f,'g') for f in (0,.5,1)]
        gutter=max(55,max(metrics.horizontalAdvance(t) for t in captions)+12)
        return QRectF(gutter,18,max(1,self.width()-gutter-14),max(1,self.height()-61))

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.plot_rect()
        bins=self.series.get('bins',[])
        values=[float(item.get('value') or 0) for item in bins]
        high=max(1,max((value for value,item in zip(values,bins) if not item.get('future')),default=0))
        p.setFont(ui_font(max(14,self.controller.prefs['font_size']-2)))
        for fraction in (0,0.5,1):
            y=rect.bottom()-rect.height()*fraction
            p.setPen(QPen(QColor(LINE),1))
            p.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y))
            p.setPen(QColor(MUTED))
            tick=compact(high*fraction) if high>=100 else format(high*fraction,'g')
            draw_count_text(p,QRectF(0,y-12,rect.left()-8,24),tick,p.font(),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        if not bins or not self.series.get('available',True):
            p.setPen(QColor(MUTED));p.setFont(ui_font(16))
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,'正在读取本机记录…')
            p.end();return
        line_mode=self.series.get('mode')=='line'
        step=rect.width()/max(1,len(bins))
        if line_mode:
            points=[]
            for index,item in enumerate(bins):
                if item.get('future'):continue
                x=rect.left()+step*(index+0.5)
                y=rect.bottom()-rect.height()*values[index]/high
                points.append(QPointF(x,y))
            from chart_curve import SmoothTrace
            path=SmoothTrace(points).path
            p.setPen(QPen(QColor(ACCENT),2.2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
        else:
            for index,value in enumerate(values):
                width=max(1,step*0.65)
                x=rect.left()+step*(index+0.5)-width/2
                h=max(1,rect.height()*value/high) if value else 0
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#a99abb' if index!=self.hover else ACCENT))
                p.drawRoundedRect(QRectF(x,rect.bottom()-h,width,h),min(3,width/2),min(3,h/2))
        p.setPen(QColor(MUTED))
        if line_mode:
            labels=[(0,'00'),(0.5,'12'),(1,'24时')]
        else:
            start=str(self.series.get('start',''))[5:].replace('-','/')
            end=str(self.series.get('end',''))[5:].replace('-','/')
            labels=[(0,start),(1,end)]
        for fraction,text in labels:
            x=rect.left()+rect.width()*fraction
            p.drawText(QRectF(x-(55 if fraction==1 else 0),rect.bottom()+10,55,22),Qt.AlignmentFlag.AlignRight if fraction==1 else Qt.AlignmentFlag.AlignLeft,text)
        if 0<=self.hover<len(bins):
            x=rect.left()+step*(self.hover+0.5)
            p.setPen(QPen(QColor('#baadc9'),1,Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom()))
        p.end()

    def mouseMoveEvent(self,event):
        bins=self.series.get('bins',[])
        rect=self.plot_rect()
        if bins and rect.contains(event.position()):
            index=min(len(bins)-1,max(0,int((event.position().x()-rect.left())/rect.width()*len(bins))))
            self.hover=index
            item=bins[index]
            suffix=' · 尚未到此时段' if item.get('future') else ' · 当前小时' if item.get('current') else ''
            self.hoverText.emit(str(item.get('label') or item.get('start') or '')+'  '+format(int(item.get('value') or 0),',')+' Token'+suffix)
            self.update()
    def leaveEvent(self,event):
        self.hover=-1;self.hoverText.emit('');self.update()

class Statistics(QWidget):
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.period='7d'
        self.mode='usage'
        self.selected_model=''
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0);layout.setSpacing(12)
        tabs=QHBoxLayout();tabs.setSpacing(5)
        self.mode_buttons={}
        for key,text in [('usage','用量'),('models','模型'),('quota','额度对比')]:
            item=button(text,'stats_'+key,lambda checked=False,k=key:self.select_mode(k))
            item.setCheckable(True);tabs.addWidget(item,1);self.mode_buttons[key]=item
        layout.addLayout(tabs)
        self.pages=QStackedWidget();layout.addWidget(self.pages,1)
        self.chart_page=QWidget();chart_layout=QVBoxLayout(self.chart_page)
        chart_layout.setContentsMargins(0,0,0,0);chart_layout.setSpacing(10)
        ranges=QHBoxLayout();ranges.setSpacing(4);self.ranges={}
        for key,text in [('day','今日'),('7d','7天'),('30d','30天'),('all','全部')]:
            item=button(text,'range_'+key,lambda checked=False,k=key:self.select_period(k),True)
            item.setCheckable(True);ranges.addWidget(item,1);self.ranges[key]=item
        chart_layout.addLayout(ranges)
        self.total=CountLabel('');self.total.setTextFormat(Qt.TextFormat.PlainText)
        self.total.setFont(ui_font(25));self.total.setStyleSheet('font-size:24px;font-weight:400;');chart_layout.addWidget(self.total)
        self.chart=SeriesChart(controller);chart_layout.addWidget(self.chart,1)
        self.readout=label('',15);self.readout.setWordWrap(True);self.readout.setMinimumHeight(38)
        self.readout.setStyleSheet('color:'+MUTED+';');chart_layout.addWidget(self.readout)
        self.chart.hoverText.connect(self.set_readout)
        self.models_scroll=QScrollArea();self.models_scroll.setWidgetResizable(True)
        self.models_body=QWidget();self.models_layout=QVBoxLayout(self.models_body)
        self.models_layout.setContentsMargins(0,0,0,0);self.models_layout.setSpacing(5)
        self.models_scroll.setWidget(self.models_body);self.models_scroll.setMinimumHeight(120)
        chart_layout.addWidget(self.models_scroll,1);self.models_scroll.hide()
        self.analogy=label('',15);self.analogy.setWordWrap(True);self.analogy.setStyleSheet('color:'+MUTED+';')
        chart_layout.addWidget(self.analogy)
        self.pages.addWidget(self.chart_page)
        self.quota_scroll=QScrollArea();self.quota_scroll.setWidgetResizable(True)
        self.quota_view=None
        self.pages.addWidget(self.quota_scroll)
        self.mode_buttons['usage'].setChecked(True)
        self._model_key=None
        self._quota_key=None

    def select_period(self,period):
        self.period=period;self.selected_model='';self.refresh(force=True)
    def select_mode(self,mode):
        self.mode=mode
        if mode=='models' and self.period=='day':self.period='7d'
        self.refresh(force=True)
        self.controller.reflow()
    def set_readout(self,text):
        if text:self.readout.setText(text)
        else:
            note='每小时消耗 · 当前小时尚未结束' if self.period=='day' else '本机可读日志 · 鼠标移到图上查看用量'
            if (self.controller.bubble.token_snapshot or {}).get('partial'):note+='\n部分记录暂不可读'
            self.readout.setText(note)

    def refresh(self,force=False):
        from token_calendar import usage_series
        from token_analytics import model_series
        snapshot=self.controller.bubble.token_snapshot or {}
        for key,item in self.mode_buttons.items():item.setChecked(key==self.mode)
        for key,item in self.ranges.items():
            item.setChecked(key==self.period);item.setEnabled(key!='day' or self.mode=='usage')
        if self.mode=='quota':
            if self.quota_view is None:
                from quota_compare_ui import QuotaCompareView
                self.quota_view=QuotaCompareView()
                self.quota_scroll.setWidget(self.quota_view)
            key=repr(snapshot.get('quota_history',{}))
            if force or key!=self._quota_key:
                self._quota_key=key;self.quota_view.set_snapshot(snapshot)
                enrich_editor(self.quota_view,self.controller.prefs['font_size'])
            self.pages.setCurrentWidget(self.quota_scroll)
            return
        self.pages.setCurrentWidget(self.chart_page)
        self.models_scroll.setVisible(self.mode=='models')
        self.analogy.setVisible(self.mode=='usage' and self.period=='all')
        if self.mode=='usage':
            series=usage_series(snapshot,self.period)
            self.chart.set_series(series)
            self.total.setText((compact(series.get('total',0)) if series.get('available') else '—')+' Token')
            if self.period=='all':
                from book_reference import analogy
                item=analogy(series.get('total',0),0)
                self.analogy.setText(str(item.get('sentence','')))
        else:
            report=dict(snapshot.get('report') or {})
            # The backend's report.day describes yesterday's daily report.
            # This panel compares calendar ranges through today, like usage.
            if report and isinstance(snapshot.get('today'),str):report['day']=snapshot['today']
            series=model_series(report,self.period)
            models=series.get('models',[])
            chosen=next((item for item in models if item.get('model')==self.selected_model),None)
            bins=[]
            for index,item in enumerate(series.get('bins',[])):
                value=item.get('values',{}).get(self.selected_model,0) if chosen else item.get('total',0)
                bins.append(dict(item,value=value,label=item.get('start','')))
            self.chart.set_series(dict(mode='bars',bins=bins,total=chosen.get('total',0) if chosen else series.get('total',0),available=bool(report),start=series.get('start',''),end=series.get('end','')))
            self.total.setText((compact(chosen.get('total',0) if chosen else series.get('total',0)) if report else '—')+' Token')
            key=(repr(models),self.selected_model)
            if force or key!=self._model_key:
                self._model_key=key;clear_layout(self.models_layout)
                if self.selected_model:
                    self.models_layout.addWidget(button('全部模型','clear_model',lambda:self.choose_model(''),True))
                total=max(1,int(series.get('total',0)))
                for item in models:
                    name=str(item.get('model','未知模型'))
                    share=100*int(item.get('total',0))/total
                    display=QFontMetrics(ui_font(self.controller.prefs['font_size'])).elidedText(name,Qt.TextElideMode.ElideRight,max(120,self.width()-24))
                    row=button(display+'\n'+compact(item.get('total',0))+' Token  ·  '+format(share,'.1f')+'%','model_'+name,lambda checked=False,m=name:self.choose_model(m),True)
                    row.setToolTip(name+'\n输入 '+compact(item.get('input',0))+' · 输出 '+compact(item.get('output',0)) if item.get('known') else name+'\n输入与输出分项记录不完整')
                    row.setMinimumWidth(0);row.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                    row.setMinimumHeight(58);row.setCheckable(True);row.setChecked(name==self.selected_model)
                    row.setStyleSheet('QPushButton{text-align:left;padding:7px;}')
                    self.models_layout.addWidget(row)
                if not models:self.models_layout.addWidget(label('该范围暂无模型记录' if report else '正在整理模型记录…',16))
                self.models_layout.addStretch(1)
        self.set_readout('')

    def choose_model(self,name):
        self.selected_model='' if name==self.selected_model else name
        self.refresh(force=True)

class DisplayPreferences(QWidget):
    def __init__(self,controller):
        super().__init__();self.controller=controller
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(15)
        title=label('面板与操作',19,True);layout.addWidget(title)
        self.combos={}
        for key,title,items in [
            ('panel_scale','面板尺寸',[('100% · 紧凑',1.0),('110% · 舒展',1.1)]),
            ('font_size','文字大小',[('16 · 标准',16),('17 · 推荐',17),('18 · 大字',18),('19 · 更大',19)]),
            ('hide_ms','离开后收回',[('0.45 秒',450),('0.7 秒',700),('1 秒',1000)])]:
            row=QHBoxLayout();row.addWidget(label(title),1)
            combo=QComboBox();combo.setObjectName('pref_'+key);combo.setMinimumHeight(36)
            for text,value in items:combo.addItem(text,value)
            combo.setCurrentIndex(max(0,combo.findData(controller.prefs[key])))
            combo.currentIndexChanged.connect(lambda index,k=key,c=combo:controller.set_preference(k,c.itemData(index)))
            row.addWidget(combo,1);layout.addLayout(row);self.combos[key]=combo
        from settings_controls import MarkedCheckBox
        reduced=MarkedCheckBox('减少动态效果');reduced.setObjectName('pref_reduced_motion')
        reduced.setChecked(controller.prefs['reduced_motion'])
        reduced.toggled.connect(lambda value:controller.set_preference('reduced_motion',value));layout.addWidget(reduced)
        help_text=label('拖动顶部可自由摆放；拖到屏幕边缘即收纳。\n靠近原位置展开，移开后沿原路收回。',16)
        help_text.setWordWrap(True);help_text.setStyleSheet('color:'+MUTED+';');layout.addWidget(help_text)
        layout.addWidget(line())
        layout.addWidget(button('人物、连接与其他设置  ›','open_original_settings',controller.open_original_settings))
        note=label('人物大小、位置和动画保持原样。',15);note.setStyleSheet('color:'+MUTED+';');note.setWordWrap(True);layout.addWidget(note)
        layout.addStretch(1)

class ActivePageStack(QStackedWidget):
    def minimumSizeHint(self):return QSize(0,0)
    def sizeHint(self):
        current=self.currentWidget()
        return current.sizeHint() if current else QSize(360,260)

class DrawerWindow(QWidget):
    def __init__(self,controller):
        flags=Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint
        if controller.owner.settings.get('on_top',True):flags|=Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None,flags)
        self.controller=controller
        self.setWindowTitle('白龙桌宠 '+VERSION+' — 面板')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFont(ui_font(controller.prefs['font_size']))
        layout=QVBoxLayout(self);layout.setContentsMargins(16,14,16,14);layout.setSpacing(12)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.header=QWidget();self.header.setObjectName('panel_drag_handle');self.header.setCursor(Qt.CursorShape.SizeAllCursor)
        header=QHBoxLayout(self.header);header.setContentsMargins(0,0,0,0);header.setSpacing(7)
        indicator=controller.bubble.status_indicator
        indicator.setParent(self);indicator.setFixedSize(22,22);indicator.show();header.addWidget(indicator)
        self.title=label('Codex',20,True);self.title.setObjectName('panel_drag_title');self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title.setStyleSheet('QPushButton{text-align:left;font-weight:600;border:0;background:transparent;padding:0;}')
        header.addWidget(self.title,1)
        refresh=controller.bubble.refresh_button
        refresh.setParent(self);refresh.setFixedSize(32,32);refresh.show();header.addWidget(refresh)
        self.pin=QToolButton();self.pin.setObjectName('edge_pin');self.pin.setText('固定');self.pin.setCheckable(True)
        self.pin.setToolTip('固定面板，移出后仍保持打开');self.pin.setAccessibleName('固定面板');self.pin.setFixedSize(48,32)
        self.pin.clicked.connect(controller.set_pinned);header.addWidget(self.pin)
        self.collapse=QToolButton();self.collapse.setObjectName('edge_collapse');self.collapse.setText('›');self.collapse.setFixedSize(28,32)
        self.collapse.setToolTip('收回到屏幕边缘');self.collapse.setAccessibleName('收回面板')
        self.collapse.clicked.connect(lambda:controller.collapse(explicit=True));header.addWidget(self.collapse)
        layout.addWidget(self.header)
        self.stack=ActivePageStack();self.stack.setObjectName('edge_pages');layout.addWidget(self.stack,1)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored)
        nav=QHBoxLayout();nav.setSpacing(4);self.nav={}
        for key,text in [('overview','概览'),('stats','统计'),('chat','聊天'),('settings','设置')]:
            item=button(text,'nav_'+key,lambda checked=False,k=key:controller.navigate(k))
            item.setCheckable(True);item.setMinimumHeight(38);nav.addWidget(item,1);self.nav[key]=item
        layout.addLayout(nav)
        self.apply_style()

    def apply_style(self):
        global FONT_BASE
        size=self.controller.prefs['font_size']
        FONT_BASE=size
        self.setFont(ui_font(size))
        self.setStyleSheet('''
            QWidget{color:'''+INK+''';font-family:"Segoe UI","Microsoft YaHei UI","Noto Sans SC";font-size:'''+str(size)+'''px;}
            QLabel,QStackedWidget,QScrollArea,QScrollArea>QWidget>QWidget{background:transparent;}
            QPushButton,QToolButton{background:transparent;border:1px solid transparent;border-radius:7px;padding:5px 8px;}
            QPushButton:hover,QToolButton:hover{background:#f0eaf5;color:#6c5589;}
            QPushButton:checked,QToolButton:checked{background:#ebe3f2;color:#6b5188;}
            QPushButton:focus,QToolButton:focus,QComboBox:focus{border:1px solid #9581b0;}
            QPushButton:pressed,QToolButton:pressed{background:#e3d8ed;}
            QPushButton:disabled,QToolButton:disabled{color:#9c95a4;}
            QToolButton#edge_pin{font-size:16px;padding:0 2px;}
            QToolButton#edge_collapse{font-size:24px;padding:0;}
            QComboBox{background:#f1edf5;border:1px solid #e4ddea;border-radius:6px;padding:5px;}
            QComboBox QAbstractItemView{background:#fbfafc;selection-background-color:#e9e0f1;}
            QLineEdit,QPlainTextEdit,QTextEdit{background:#fff;border:1px solid #ded5e6;border-radius:6px;padding:6px;}
            QScrollArea{border:0;}
            QScrollBar:vertical{background:transparent;width:9px;margin:0;}
            QScrollBar::handle:vertical{background:#c8bbd7;border-radius:4px;min-height:32px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}
        ''')
        self.collapse.setFont(ui_font(25))
        self.pin.setFont(ui_font(15))

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(SURFACE));p.setPen(QPen(QColor('#dfd7e8'),1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5,0.5,-0.5,-0.5),14,14)
        p.end()

    def closeEvent(self,event):
        if getattr(self.controller.owner,'closing',False) or getattr(self.controller.owner,'_codex_closing',False):
            self.controller.shutdown();event.accept();return
        event.ignore();self.controller.collapse(explicit=True)

class EdgeHandle(QWidget):
    def __init__(self,controller):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.controller=controller
        self.setWindowTitle('白龙面板 · 边缘唤醒')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('停留展开白龙面板')
        self.setAccessibleName('白龙面板边缘唤醒条')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#a66d87' if self.controller.bubble.status_indicator.unread else '#a99ab9'))
        if self.width()>self.height():rect=QRectF(12,0,self.width()-24,3)
        else:rect=QRectF(0,12,3,self.height()-24)
        p.drawRoundedRect(rect,1.5,1.5);p.end()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.controller.expand()

class EdgeController(QObject):
    def __init__(self,owner,bubble,test_mode=False):
        super().__init__(owner)
        self.owner=owner;self.bubble=bubble;self.test_mode=test_mode
        self.prefs=preferences();self.pinned=False;self.progress=1.0
        self.dock=self.prefs.get('dock') if self.prefs.get('dock') in ('left','right','top','bottom') else None
        self._drag=None;self._dismissed=False
        from dock_motion import Spring
        self.spring=Spring(1.)
        self.target=1.0;self.hover_started=None;self.leave_started=None
        self.dirty=True;self.last_refresh=0.0;self.last_key=0.0
        self._last_unread=None
        self.current_page='overview';self.pages={};self._report_opening=False
        self.window=DrawerWindow(self);self.handle=EdgeHandle(self)
        self.animation=QTimer(self);self.animation.setInterval(16)
        self.animation.setTimerType(Qt.TimerType.PreciseTimer)
        self.animation.timeout.connect(self.motion_frame)
        self.overview=Overview(self)
        overview_scroll=QScrollArea();overview_scroll.setWidgetResizable(True)
        overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overview.setMinimumHeight(self.overview.minimumSizeHint().height())
        overview_scroll.setWidget(self.overview)
        self.pages['overview']=overview_scroll
        self.window.stack.addWidget(overview_scroll)
        self.window.nav['overview'].setChecked(True)
        self.statistics=None;self.settings_page=None;self.details_page=None
        self._reflowing=False;self._screen_signature=None
        self.reflow()
        self.timer=QTimer(self);self.timer.setInterval(60);self.timer.timeout.connect(self.poll)
        QApplication.instance().installEventFilter(self)
        if not test_mode:
            save_preferences(self.prefs)
            self.timer.start()
            QTimer.singleShot(0,self.expand)
        _controllers.append(self)

    def screen(self):
        screens=QApplication.screens()
        name=self.prefs.get('screen')
        return next((s for s in screens if s.name()==name),None) or QApplication.primaryScreen()

    def desired_size(self):
        area=self.screen().availableGeometry();density=self.prefs['panel_scale']
        width=416 if self.current_page in ('overview','settings') else 520
        target={'overview':414,'stats':580,'settings':500,'chat':640,'original_settings':680,'details':620}.get(self.current_page,580)
        return QSize(min(round(width*density),area.width()-24),min(round(target*density),area.height()-24))

    def reflow(self):
        if self._reflowing or self._drag:return
        self._reflowing=True
        try:
            area=self.screen().availableGeometry();size=self.desired_size()
            saved=self.prefs.get('position')
            x,y=(saved if isinstance(saved,list) and len(saved)==2 else [area.right()-size.width()-24,area.top()+80])
            x=max(area.left(),min(int(x),area.right()-size.width()+1))
            y=max(area.top(),min(int(y),area.bottom()-size.height()+1))
            self.open_rect=QRect(x,y,size.width(),size.height())
            anchor=self.prefs['handle_position']
            if self.dock in ('left','right'):
                y=max(area.top(),min(round(area.top()+area.height()*anchor-size.height()/2),area.bottom()-size.height()+1))
                x=area.left() if self.dock=='left' else area.right()-size.width()+1
                self.open_rect.moveTo(x,y)
                cx=area.left() if self.dock=='left' else area.right()+1
                self.closed_point=QPoint(cx-size.width() if self.dock=='left' else cx,y)
                center=max(area.top()+42,min(round(area.top()+area.height()*anchor),area.bottom()-42))
                hx=area.left() if self.dock=='left' else area.right()-5
                self.handle.setGeometry(hx,center-42,6,84)
                self.hot_rect=QRect(hx-3,center-46,12,92)
            elif self.dock in ('top','bottom'):
                x=max(area.left(),min(round(area.left()+area.width()*anchor-size.width()/2),area.right()-size.width()+1))
                y=area.top() if self.dock=='top' else area.bottom()-size.height()+1
                self.open_rect.moveTo(x,y)
                cy=area.top() if self.dock=='top' else area.bottom()+1
                self.closed_point=QPoint(x,cy-size.height() if self.dock=='top' else cy)
                center=max(area.left()+42,min(round(area.left()+area.width()*anchor),area.right()-42))
                hy=area.top() if self.dock=='top' else area.bottom()-5
                self.handle.setGeometry(center-42,hy,84,6)
                self.hot_rect=QRect(center-46,hy-3,92,12)
            else:
                self.closed_point=self.open_rect.topLeft();self.hot_rect=QRect()
            self.window.ensurePolished();self.window.layout().activate()
            self.window.setFixedSize(size)
            self._advance(self.progress)
            self.window.collapse.setText({'left':'‹','right':'›','top':'⌃','bottom':'⌄'}.get(self.dock,'›'))
            self.window.collapse.setToolTip('收回边缘' if self.dock else '收纳到最近边缘')
            self.handle.update()
            self._screen_signature=(self.screen().name(),tuple(area.getRect()))
        finally:self._reflowing=False

    def _advance(self,value):
        self.progress=max(0.,min(1.,float(value)))
        a=self.closed_point;b=self.open_rect.topLeft()
        self.window.move(round(a.x()+(b.x()-a.x())*self.progress),round(a.y()+(b.y()-a.y())*self.progress))

    def motion_frame(self):
        now=time.perf_counter();dt=now-self.motion_clock;self.motion_clock=now
        self._advance(self.spring.advance(dt))
        if self.spring.settled:
            self.animation.stop();self._finished()

    def _finished(self):
        if self.target==0.:
            self.progress=0.;self.window.hide();self.bubble.panel_page='status'
            if not self.test_mode:self.handle.show()
        else:
            self.progress=1.;self.window.move(self.open_rect.topLeft());self.handle.hide()

    def animate_to(self,target):
        self.target=float(target);self.spring.target=float(target)
        if target:
            self.bubble.panel_page='chat' if self.current_page=='chat' else 'settings' if self.current_page=='original_settings' else 'status'
            self.reflow();self.refresh(force=True)
            self.window.show();self.window.raise_();self.handle.hide()
        from settings_controls import motion_enabled
        if self.prefs['reduced_motion'] or not motion_enabled() or not self.dock:
            self.animation.stop();self.spring.value=float(target);self.spring.velocity=0.
            self._advance(target);self._finished();return
        if not self.animation.isActive():
            self.motion_clock=time.perf_counter();self.animation.start()

    def save_position(self):
        self.prefs.update(dock=self.dock,screen=self.screen().name(),position=[self.open_rect.x(),self.open_rect.y()])
        save_preferences(self.prefs)

    def finish_drag(self):
        rect=self.window.geometry();screen=QApplication.screenAt(rect.center()) or self.screen()
        self.prefs['screen']=screen.name();area=screen.availableGeometry()
        distances={'left':rect.left()-area.left(),'right':area.right()-rect.right(),
                   'top':rect.top()-area.top(),'bottom':area.bottom()-rect.bottom()}
        edge=min(distances,key=distances.get)
        self.dock=edge if distances[edge]<=22 else None
        self.prefs['position']=[rect.x(),rect.y()]
        if self.dock:
            self.prefs['handle_position']=max(0.,min(1.,(rect.center().y()-area.top())/area.height() if self.dock in ('left','right') else (rect.center().x()-area.left())/area.width()))
        self.progress=self.spring.value=self.target=self.spring.target=1.;self.spring.velocity=0.
        self.reflow();self.save_position()
        if self.dock:self.collapse(explicit=True)

    def expand(self):
        self.hover_started=self.leave_started=None
        if self.target!=1 or not self.window.isVisible():self.animate_to(1)

    def collapse(self,explicit=False):
        if self._drag:return
        if not self.dock:
            if not explicit:return
            rect=self.window.geometry();area=self.screen().availableGeometry()
            self.dock=min({'left':rect.left()-area.left(),'right':area.right()-rect.right(),'top':rect.top()-area.top(),'bottom':area.bottom()-rect.bottom()},key=lambda e:abs({'left':rect.left()-area.left(),'right':area.right()-rect.right(),'top':rect.top()-area.top(),'bottom':area.bottom()-rect.bottom()}[e]))
            self.prefs['handle_position']=(rect.center().y()-area.top())/area.height() if self.dock in ('left','right') else (rect.center().x()-area.left())/area.width()
            self.reflow();self.save_position()
        if explicit:self.set_pinned(False);self._dismissed=True
        if self.target!=0 or self.progress>0:self.animate_to(0)
        self.hover_started=self.leave_started=None

    def set_pinned(self,value):
        self.pinned=bool(value)
        self.window.pin.setChecked(self.pinned)
        self.window.pin.setText('已固定' if self.pinned else '固定')
        self.window.pin.setFixedWidth(62 if self.pinned else 48)
        if self.pinned:self.expand()

    def popup_active(self):
        for widget in (QApplication.activePopupWidget(),QApplication.activeModalWidget()):
            while widget is not None:
                if widget is self.window:return True
                widget=widget.parentWidget()
        return False

    def ensure_above_character(self):
        """Repair only overlap with our own Tool window, without taking focus."""
        if not self.window.isVisible() or not self.owner.isVisible():return
        overlap=self.window.geometry().intersected(self.owner.geometry())
        if overlap.isEmpty():return
        hit=QApplication.widgetAt(overlap.center())
        if hit is self.owner or (hit is not None and self.owner.isAncestorOf(hit)):
            self.window.raise_()

    def tick(self,position,now=None,popup=False):
        if not self.dock or self._drag:return
        now=time.monotonic() if now is None else now
        hot=self.hot_rect.contains(position)
        inside=self.window.isVisible() and self.window.geometry().contains(position)
        if self._dismissed:
            if hot or inside:return
            self._dismissed=False
        if self.progress==0 and self.target==0:
            if hot:
                if self.hover_started is None:self.hover_started=now
                elif (now-self.hover_started)*1000>=self.prefs['hover_ms']:self.expand()
            else:self.hover_started=None
            return
        if inside or hot or self.pinned or popup or now-self.last_key<1.5:
            self.leave_started=None
            if self.target==0 and (inside or hot):self.expand()
        else:
            if self.leave_started is None:self.leave_started=now
            elif (now-self.leave_started)*1000>=self.prefs['hide_ms']:self.collapse()

    def poll(self):
        interval=80 if self.dock and self.progress==0 else 120 if self.dock else 250
        if self.timer.interval()!=interval:self.timer.setInterval(interval)
        if getattr(self.owner,'_desktop_hidden',False) or not self.bubble.enabled:
            self.window.hide();self.handle.hide();self.progress=self.target=0.0;self.animation.stop();return
        if getattr(self.owner,'_video_yielded',False) or getattr(self.owner,'_fullscreen_yielded',False):
            self.collapse();self.handle.hide();return
        wanted=bool(self.owner.settings.get('on_top',True))
        actual=bool(self.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if wanted!=actual:
            visible=self.window.isVisible()
            self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,wanted)
            if visible:self.window.show()
        area=self.screen().availableGeometry()
        signature=(self.screen().name(),tuple(area.getRect()))
        if signature!=self._screen_signature:self.reflow()
        if self.dock and self.progress==0 and not self.handle.isVisible():self.handle.show()
        unread=self.bubble.status_indicator.unread
        if unread!=self._last_unread:self._last_unread=unread;self.handle.update()
        self.tick(QCursor.pos(),popup=self.popup_active())
        self.ensure_above_character()
        if self.window.isVisible() and time.monotonic()-self.last_refresh>0.5:self.refresh()

    def eventFilter(self,obj,event):
        if obj is self.owner and event.type() in (QEvent.Type.Show,QEvent.Type.WindowActivate):
            QTimer.singleShot(0,self.ensure_above_character)
        if obj is self.window.header:
            if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
                self.animation.stop();self._drag=(event.globalPosition().toPoint(),self.window.pos())
                self.handle.hide();self.window.header.grabMouse();return True
            if event.type()==QEvent.Type.MouseMove and self._drag:
                delta=event.globalPosition().toPoint()-self._drag[0]
                self.window.move(self._drag[1]+delta);return True
            if event.type()==QEvent.Type.MouseButtonRelease and self._drag:
                self._drag=None;self.window.header.releaseMouse();self.finish_drag();return True
        if event.type()==QEvent.Type.KeyPress:
            widget=obj
            if isinstance(widget,QWidget) and (widget is self.window or self.window.isAncestorOf(widget)):
                self.last_key=time.monotonic()
                if event.key()==Qt.Key.Key_Escape:
                    self.collapse(explicit=True);return True
        if event.type()==QEvent.Type.MouseButtonPress:
            widget=obj
            if isinstance(widget,QWidget) and (widget is self.window or self.window.isAncestorOf(widget)):
                self.last_key=time.monotonic()
        return False

    def mark_dirty(self):self.dirty=True

    def refresh(self,force=False):
        self.last_refresh=time.monotonic()
        if not force and not self.dirty:
            if self.current_page=='overview':self.overview.quotas.refresh()
            return
        self.dirty=False
        if self.current_page=='overview':self.overview.refresh()
        elif self.current_page=='stats' and self.statistics:self.statistics.refresh(force=force)
        # Editor typography is applied once on attach/tab change, never each refresh.

    def navigate(self,page):
        if page=='chat':
            self.owner.open_chat();return
        if page=='stats':
            if self.statistics is None:
                self.statistics=Statistics(self);self.pages['stats']=self.statistics;self.window.stack.addWidget(self.statistics)
            self.ensure_report()
        elif page=='settings' and self.settings_page is None:
            self.settings_page=DisplayPreferences(self);self.pages['settings']=self.settings_page;self.window.stack.addWidget(self.settings_page)
        elif page=='details':
            self.show_details();return
        self.current_page=page
        self.bubble.panel_page='status' if page in ('overview','stats','details') else 'settings'
        self.window.stack.setCurrentWidget(self.pages[page])
        self.window.title.setText({'overview':'Codex','stats':'用量统计','settings':'面板设置'}.get(page,'白龙'))
        for key,item in self.window.nav.items():item.setChecked(key==page)
        self.reflow();self.expand();self.refresh(force=True)

    def ensure_report(self):
        # Native statistics consumes the same background snapshot directly.
        # Do not construct the legacy animated report/window on a click.
        if not self.test_mode:QTimer.singleShot(0,self.owner.refresh_report)

    def show_tokens(self,period):
        self.navigate('stats');self.statistics.select_mode('usage');self.statistics.select_period(period)

    def show_details(self):
        from detail_sections import DetailsTabs
        if self.details_page is not None:
            self.window.stack.removeWidget(self.details_page);self.details_page.deleteLater()
        tabs=DetailsTabs(self.bubble)
        self.details_page=tabs;self.pages['details']=tabs;self.window.stack.addWidget(tabs)
        enrich_editor(tabs,self.prefs['font_size'])
        tabs.setMinimumHeight(0);tabs.setMaximumHeight(16777215)
        self.current_page='details';self.bubble.panel_page='status'
        self.window.stack.setCurrentWidget(tabs);self.window.title.setText('状态与额度')
        for key,item in self.window.nav.items():item.setChecked(key=='overview')
        self.reflow();self.expand()

    def open_original_settings(self):self.owner.open_settings()

    def attach_editor(self,key,widget):
        page='original_settings' if key=='settings' else 'chat'
        if self.window.stack.indexOf(widget)<0:self.window.stack.addWidget(widget)
        widget.setWindowFlags(Qt.WindowType.Widget)
        if widget.layout():widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        widget.setMinimumSize(0,0);widget.setMaximumSize(16777215,16777215)
        self.pages[page]=widget
        self.current_page=page;self.bubble.panel_page=key
        self.window.stack.setCurrentWidget(widget);widget.show()
        if key=='settings':
            adapt_settings(widget,self.prefs['font_size'])
            if not widget.property('edgeTabsLinked'):
                widget.setProperty('edgeTabsLinked',True)
                widget.tabs.currentChanged.connect(lambda index:QTimer.singleShot(0,lambda:adapt_settings(widget,self.prefs['font_size'])))
        else:
            enrich_editor(widget,self.prefs['font_size'])
            if hasattr(widget,'pages') and not widget.property('edgeTabsLinked'):
                widget.setProperty('edgeTabsLinked',True)
                widget.pages.currentChanged.connect(lambda index:QTimer.singleShot(0,lambda:enrich_editor(widget,self.prefs['font_size'])))
        self.window.title.setText('白龙设置' if key=='settings' else '和白龙聊天')
        for name,item in self.window.nav.items():item.setChecked(name==key)
        self.reflow();self.expand();self.window.activateWindow()
        if key=='chat' and hasattr(widget,'input'):widget.input.setFocus()

    def set_preference(self,key,value):
        self.prefs[key]=value;save_preferences(self.prefs)
        if key=='reduced_motion':
            os.environ['BAILONG_REDUCED_MOTION']='1' if value else '0'
            from settings_controls import motion_enabled
            motion_enabled.cache_clear()
        if key=='font_size':
            self.window.apply_style()
            for widget in [self.overview,self.settings_page,self.statistics]:
                if widget:
                    for child in [widget]+widget.findChildren(QLabel):child.setFont(ui_font(value))
            if self.statistics:self.statistics.total.setFont(ui_font(value+7,True))
        self.reflow();self.refresh(force=True)

    def shutdown(self):
        self.timer.stop();self.animation.stop();self.window.hide();self.handle.hide()
        QApplication.instance().removeEventFilter(self)

    def qa_capture(self,directory):
        """Only used by an isolated local fixture; no chat is sent or setting applied."""
        destination=Path(directory)
        destination.mkdir(parents=True,exist_ok=True)
        self.set_pinned(True)
        def shot(name):self.window.grab().save(str(destination/(name+'.png')))
        def models():self.statistics.select_mode('models')
        def quota():self.statistics.select_mode('quota')
        sequence=[(100,lambda:(self.navigate('overview'),shot('overview'))),
                  (450,lambda:self.navigate('stats')),
                  (850,lambda:shot('usage')),
                  (1000,models),(1200,lambda:shot('models')),
                  (1350,quota),(1550,lambda:shot('quota')),
                  (1700,self.owner.open_settings),(2050,lambda:shot('settings')),
                  (2200,self.owner.open_chat),(2550,lambda:shot('chat')),
                  (2750,lambda:self.navigate('overview')),(3100,lambda:shot('overview-latest'))]
        for delay,action in sequence:QTimer.singleShot(delay,action)
