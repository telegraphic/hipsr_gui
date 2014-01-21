#!/usr/bin/env python
"""
hipsr_gui.py
===========

This script starts a Qt4 + matplotlib based graphical user interface for monitoring HIPSR's data output.

Requirements
------------
PyQt4 (or PySide), for Qt4 bindings
numpy, matplotlib.

TODO: 
----- 
* Zoom in on selected area
* Tabbed versions
* Pause & explore plot
* save image
* show which beam is which

"""

__version__ = "0.1"
__author__  = "Danny Price"

# Imports
import sys, os
import socket
import json                     # Pack/unpack python dictionaries over UDP 
from collections import deque   # Ring buffer
from optparse import OptionParser

try:
    print "Using uJson"
    import ujson as json
except:
    print "Warning: uJson not installed. Reverting to python's native Json (slower)"
    import json

try:
    import hipsr_core.qt_compat as qt_compat
    QtCore   = qt_compat.QtCore
    QtGui    = qt_compat.import_module("QtGui")
    QtNetwork = qt_compat.import_module("QtNetwork")
except:
    print "Error: cannot load PySide or PyQt4. Please check your install."
    raise

import numpy as np

import matplotlib
if matplotlib.__version__ == '0.99.3':
    print "Error: your matplotlib version is too old to run this. Please upgrade."
    exit()
else:
    matplotlib.use('Qt4Agg')
    if qt_compat.USES_PYSIDE:
        print "Using PySide-Matplotlib"
        matplotlib.rcParams['backend.qt4']='PySide'
    else:
        print "Using PyQt4-Matplotlib"
        matplotlib.rcParams['backend.qt4']='PyQt4'
    from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    import matplotlib.gridspec as gridspec
try:
    import pylab as plt
except:
    print "Error: cannot load Pylab. Check your matplotlib install."
    exit()


nbeams = 5
ntime = 120

class SettingsWindow(QtGui.QWidget):
    def __init__(self):
        super(SettingsWindow, self).__init__()
        hostLabel     = QtGui.QLabel("Host:")
        self.hostEdit = QtGui.QLineEdit()
        portLabel     = QtGui.QLabel("Port:")
        self.portEdit = QtGui.QLineEdit()
        self.okButton = QtGui.QPushButton("OK", self)
        self.okButton.clicked.connect(self.updateSettings)
        
        self.host = options.hostip
        self.port = options.hostport
        
        settingsLayout = QtGui.QGridLayout()
        settingsLayout.addWidget(hostLabel, 0, 0)
        settingsLayout.addWidget(self.hostEdit, 0, 1)
        settingsLayout.addWidget(portLabel, 1, 0)
        settingsLayout.addWidget(self.portEdit, 1, 1)
        settingsLayout.addWidget(self.okButton, 2, 1)
        
        self.setLayout(settingsLayout)
        self.setWindowTitle("Settings")
        
        self.hostEdit.setText(self.host)
        self.portEdit.setText(str(self.port))
        
        self.hostEdit.setReadOnly(True)
        self.portEdit.setReadOnly(True)
        
    def updateSettings(self):
        self.host = self.hostEdit.text()
        self.port = self.portEdit.text()
        self.hide()
    
    def toggle(self):
        if self.isVisible(): self.hide()
        else: self.show()
        

class HipsrGui(QtGui.QMainWindow):
    """ HIPSR GUI class
    
    A Qt4 Widget that uses matplotlib to display data from UDP packets.    
    """
    def __init__(self):
        super(HipsrGui, self).__init__()
        
        # Initialize user interface
        self.initUI(width=1024, height=768)

        # Setup UDP port
        self.host = options.hostip
        self.port = options.hostport
        self.udpCount = 0
        self.udpBuffer = deque(maxlen=100)

        print "Listening on %s port %s..."%(self.host, self.port)        
        self.udpServer = QtNetwork.QUdpSocket(self)
        self.udpServer.bind(QtNetwork.QHostAddress(self.host), self.port)
        self.udpServer.readyRead.connect(self.bufferUDPData)
    
    def keyLookup(self, key, data):
        """ A pythonic case statement that searches for keys in a dict. """
        
        return {
            "tcs-bandwidth": self.keyTcsBandwidth,
            "tcs-frequency": self.keyTcsFrequency,
            "beam_01" : self.keyBeam,
            "beam_02" : self.keyBeam,
            "beam_03" : self.keyBeam,
            "beam_04" : self.keyBeam,
            "beam_05" : self.keyBeam,
            "beam_06" : self.keyBeam,
            "beam_07" : self.keyBeam,
            "beam_08" : self.keyBeam,
            "beam_09" : self.keyBeam,
            "beam_10" : self.keyBeam,
            "beam_11" : self.keyBeam,
            "beam_12" : self.keyBeam,
            "beam_13" : self.keyBeam,

            }.get(str(key), self.keyNoMatch)(key, data)    # setNoMatch is default if cmd not found
    
    def keyNoMatch(self, key, data=0):
        print "Info: Unexpected key encountered."
    
    def keyTcsFrequency(self, key, data):
        """ Update plots with new TCS Frequency """
        self.sb_c_freq =  float(data[key])
        cf = self.sb_c_freq
        bw = np.abs(self.sb_bandwidth)
        
        x_data = np.linspace(cf-bw/2, cf+bw/2, 256)
        self.sb_xpol.set_xdata(x_data)
        self.sb_ypol.set_xdata(x_data)
        self.sb_ax.set_xlabel("Frequency (MHz)")
        self.sb_ax.set_xlim(cf-bw/2, cf+bw/2)
        
        wf_ticks = np.linspace(cf-bw/2, cf+bw/2, 256)[::32]
        self.wf_ax.set_xlabel("Frequency (MHz)")
        self.wf_ax.set_xticks(range(0,256)[::32])
        self.wf_ax.set_xticklabels([int(t) for t in wf_ticks])
        
        for beam in ["beam_09", "beam_10"]:
            self.mb_ax[beam].set_xlabel("Frequency (MHz)")
            self.mb_ax[beam].set_xticks(range(0,256)[::32])
            self.mb_ax[beam].set_xticklabels([int(t) for t in wf_ticks], rotation=45)

    def keyTcsBandwidth(self, key, data):
        """ Update with new TCS bandwidth """
        self.sb_bandwidth =  float(data[key])
    
    def keyBeam(self, key, data):
        """ Update plots with beam data """
        if self.sb_bandwidth < 0:
            xx = data[key]["xx"][::-1]
            yy = data[key]["yy"][::-1]
        else: 
            xx = data[key]["xx"]
            yy = data[key]["yy"]
        self.mb_xpols[key].set_ydata(xx)
        self.mb_ypols[key].set_ydata(yy)
        dmax, dmin = np.max([xx[1:-1], yy[1:-1]])*1.1, np.min([xx[1:-1], yy[1:-1]])*0.9
        self.mb_ax[key].set_ylim(dmin, dmax)
        self.updateOverallPowerPlot(key, np.array(xx).sum(), np.array(yy).sum())
        self.updateTimeSeriesData(key, xx)
        
        if key == self.activeBeam:
            self.updateSingleBeamPlot(xx, yy)
            self.updateWaterfallPlot()
    
    def modifyUDPSocket(self):
        self.udpServer.close()
        self.udpServer(QtNetwork.QHostAddress(self.host), self.port)
        self.udpServer.readyRead.connect(self.bufferUDPData)

    def initUI(self, width=1200, height=750):
        """ Initialize the User Interface 
        
        Parameters
        ----------
        width: int
            width of the UI, in pixels. Defaults to 1024px
        height: int
            height of the UI, in pixels. Defaults to 768px
        """
        
        # Create plots
        self.mb_fig, self.mb_ax, self.mb_xpols, self.mb_ypols = self.createMultiBeamPlot()
        self.sb_fig, self.sb_ax, self.sb_xpol,  self.sb_ypol, self.sb_title = self.createSingleBeamPlot()
        self.p_fig, self.p_ax, self.p_lines = self.createOverallPowerPlot()
        self.wf_fig, self.wf_ax, self.wf_imshow, self.wf_data, self.wf_colorbar = self.createWaterfallPlot()
        
        self.sb_c_freq    = 1355.0
        self.sb_bandwidth = -400.0
        
        # generate the canvas to display the plot
        self.mb_canvas = FigureCanvas(self.mb_fig)
        self.sb_canvas = FigureCanvas(self.sb_fig)
        self.p_canvas  = FigureCanvas(self.p_fig)
        self.wf_canvas = FigureCanvas(self.wf_fig)
        
        self.settings_window = SettingsWindow()
        self.settings_window.hide()
        
        # Create combo box for beam selection        
        combo = QtGui.QComboBox(self)
        combo.activated[str].connect(self.onBeamSelect)    
        self.activeBeam = "beam_01"
        self.time_series_data = {}
        
        beam_ids = ["beam_01","beam_02","beam_03","beam_04","beam_05","beam_06","beam_07", "beam_08","beam_09","beam_10","beam_11","beam_12","beam_13"]        
        for beam in beam_ids: 
            combo.addItem(beam)
            self.time_series_data[beam] = np.ones([150,256])
        
        # Widget layout
        self.sb_widget = QtGui.QWidget()
        self.sb_mpl_toolbar = NavigationToolbar(self.sb_canvas, self.sb_widget)
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(combo)
        vbox.addWidget(self.sb_canvas)
        vbox.addWidget(self.sb_mpl_toolbar)
        self.sb_widget.setLayout(vbox)
        self.sb_dock = QtGui.QDockWidget("Beam scope", self)
        self.sb_dock.setWidget(self.sb_widget)
                
        self.wf_widget = QtGui.QWidget()
        self.wf_thr = 3
        self.wf_mpl_toolbar = NavigationToolbar(self.wf_canvas, self.wf_widget)
        self.wf_line_edit = QtGui.QLineEdit()
        self.wf_line_edit.setToolTip("No. of stdev from average")
        self.wf_line_edit.setValidator(QtGui.QDoubleValidator(-999.0, 999.0, 2, self.wf_line_edit))
        self.wf_set_button = QtGui.QPushButton("Set", self)
        self.wf_set_button.clicked.connect(self.updateWaterfallThreshold)
        self.wf_line_edit.setText(str(self.wf_thr))
        wf_label = QtGui.QLabel("Color scaling:")
        
        hbox = QtGui.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(wf_label)
        hbox.addWidget(self.wf_line_edit)
        hbox.addWidget(self.wf_set_button)
        
        vbox = QtGui.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.wf_canvas)
        vbox.addWidget(self.wf_mpl_toolbar)
        self.wf_widget.setLayout(vbox)
        self.wf_dock = QtGui.QDockWidget("Waterfall plot", self)
        self.wf_dock.setWidget(self.wf_widget)

        self.p_widget = QtGui.QWidget()
        self.p_mpl_toolbar = NavigationToolbar(self.p_canvas, self.p_widget)
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.p_canvas)
        vbox.addWidget(self.p_mpl_toolbar)
        self.p_widget.setLayout(vbox)            
        self.p_dock = QtGui.QDockWidget("Power monitor", self)
        self.p_dock.setWidget(self.p_widget)
        
        # Add widgets to main window        
        self.setCentralWidget(self.mb_canvas)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.sb_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.p_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.wf_dock)
        self.wf_dock.hide(), self.sb_dock.hide(), self.p_dock.hide()
        
        # Add toolbar icons
        
        abspath = os.path.dirname(os.path.realpath(__file__))
        exitAction = QtGui.QAction(QtGui.QIcon(os.path.join(abspath, 'icons/exit.png')), 'Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)
        sbAction   = QtGui.QAction(QtGui.QIcon(os.path.join(abspath, 'icons/monitor.png')), 'Beam monitor', self)
        sbAction.triggered.connect(self.toggleSingleBeamPlot)
        pAction    = QtGui.QAction(QtGui.QIcon(os.path.join(abspath, 'icons/power.png')), 'Power monitor', self)
        pAction.triggered.connect(self.toggleOverallPowerPlot)
        wfAction    = QtGui.QAction(QtGui.QIcon(os.path.join(abspath, 'icons/spectrum.png')), 'Waterfall plot', self)
        wfAction.triggered.connect(self.toggleWaterfallPlot)
        settingsAction = QtGui.QAction(QtGui.QIcon(os.path.join(abspath, 'icons/settings.png')), 'Change config', self)
        settingsAction.triggered.connect(self.settings_window.toggle)
        
        self.toolbar = self.addToolBar("HIPSR toolbar")
        self.toolbar.addAction(exitAction)
        self.toolbar.addAction(sbAction)
        self.toolbar.addAction(pAction)
        self.toolbar.addAction(wfAction)
        self.toolbar.addAction(settingsAction)
         
        self.setGeometry(300, 300, width, height)
        self.setWindowTitle('HIPSR GUI')    
        self.show()

        
    def toggleWaterfallPlot(self):
        """ Toggles the visibility of a dock widget """
        if self.wf_dock.isVisible(): self.wf_dock.hide()
        else: self.wf_dock.show()

    def toggleSingleBeamPlot(self):
        """ Toggles the visibility of a dock widget """
        if self.sb_dock.isVisible(): self.sb_dock.hide()
        else: self.sb_dock.show()

    def toggleMultiBeamPlot(self):
        """ Toggles the visibility of a dock widget """
        if self.mb_dock.isVisible(): self.mb_dock.hide()
        else: self.mb_dock.show()

    def toggleOverallPowerPlot(self):
        """ Toggles the visibility of a dock widget """
        if self.p_dock.isVisible(): self.p_dock.hide()
        else: self.p_dock.show()
        
    def bufferUDPData(self):
        """ A circular buffer for incoming UDP packets """
        initialized = False
        while self.udpServer.hasPendingDatagrams():
            datagram, host, port = self.udpServer.readDatagram(self.udpServer.pendingDatagramSize())
            
            try:
                self.udpBuffer.append(datagram.data())
            except:
                self.udpBuffer.append(datagram)
            
            self.udpCount += 1
            #print self.udpCount
            
            if self.udpCount == 13:
                self.updateAllPlots()
       
       
    def onBeamSelect(self, beam):
        """ Beam selection combo box actions"""
        self.activeBeam = beam
        self.sb_title.set_text("Beam monitor: %s"%beam)
        self.updateAllPlots()

    def createSingleBeamPlot(self, numchans=256, beamid='beam_01'):
        """ Creates a single pylab plot for HIPSR data. """

        fig = plt.figure(figsize=(3,4),dpi=80)
        xpol_color = '#00CC00'
        ypol_color = '#CC0000'
        title = fig.suptitle("Beam monitor: %s"%beamid)
        title.set_fontsize(14)
        ax = plt.subplot(111)

        xpol, = ax.plot(np.cumsum(np.ones(numchans)),np.ones(numchans), color=xpol_color)
        ypol, = ax.plot(np.cumsum(np.ones(numchans)),np.ones(numchans), color=ypol_color)
        
        # Format plot
        ax.set_ylim(0, 2)
        ax.set_xlim(0,numchans)
        ax.set_xlabel("Channel (-)")
        ax.set_ylabel("Power (-)")  
        
        # Set border colour  
        for child in ax.get_children():
          if isinstance(child, matplotlib.spines.Spine):
            child.set_color('#666666')
              
        fig.canvas.draw()
        self.sb_max = 2
        self.sb_min = 0
      
        return fig, ax, xpol, ypol, title
    

    def createWaterfallPlot(self):
        """ Creates a single imshow plot for HIPSR data. """
        fig  = plt.figure(figsize=(3,4),dpi=80)
        ax   = plt.subplot(111)
        data = np.zeros([150,256])
        data[0] = np.ones_like(data[0]) * 100
        wf   = ax.imshow(data, cmap=plt.cm.gist_heat_r)
        
        ax.set_ylabel("Elapsed Time (m)")
        ax.set_yticks([0,30,60,90,120,150])
        ax.set_yticklabels([5,4,3,2,1,0])
        ax.set_xlabel("Channel")
        #ax.set_aspect(256./150)
        
        cb = fig.colorbar(wf)
        cb.set_clim(0,80)
        cb.set_label("Power (-)")
        #cb.set_ticks([0,2,4,6,8,10])
        fig.canvas.draw()
        
        return fig, ax, wf, data, cb
        
    def createMultiBeamPlot(self, numchans=256):
          """ Creates 13 subplots in a hexagonal array representing the multibeam feeds """
     
          fig = plt.figure(figsize=(3,4),dpi=80)
          
          # Label the plots. There's gotta be a better way...
          fig.text(0.53, 0.46, "01", size=20)
          fig.text(0.53, 0.46+0.15, "06", size=20)
          fig.text(0.53, 0.46-0.15, "03", size=20)
          fig.text(0.53+0.15, 0.46-0.075, "04", size=20)
          fig.text(0.53+0.15, 0.46+0.075, "05", size=20)
          fig.text(0.53+0.15, 0.46-0.075-0.15, "10", size=20)
          fig.text(0.53+0.15, 0.46+0.075+0.15, "12", size=20)
          fig.text(0.53-0.15, 0.46-0.075, "02", size=20)
          fig.text(0.53-0.15, 0.46+0.075, "07", size=20)
          fig.text(0.53-0.15, 0.46-0.075-0.15, "09", size=20)
          fig.text(0.53-0.15, 0.46+0.075+0.15, "13", size=20)
          fig.text(0.53-0.3, 0.46, "08", size=20)
          fig.text(0.53+0.3, 0.46, "11", size=20)
          
          xpol_color = '#00CC00'
          ypol_color = '#CC0000'
      
          title = fig.suptitle("Multibeam monitor")
          title.set_fontsize(20)
          
          # Create 13 subplots arranged on a hexagonal grid
          plotSize = 4
          gridSize = 5*plotSize+1
          gs = gridspec.GridSpec(gridSize, gridSize)
          def beam(posx, posy, size): return gs[posx-size:posx+size, posy-size:posy+size]
          ax1 = plt.subplot(beam(gridSize/2,gridSize/2,plotSize/2))
          ax3 = plt.subplot(beam(gridSize/2+plotSize,gridSize/2,plotSize/2))
          ax6 = plt.subplot(beam(gridSize/2-plotSize,gridSize/2,plotSize/2))
          ax13 = plt.subplot(beam(gridSize/2-3*plotSize/2,gridSize/2-plotSize,plotSize/2))
          ax7  = plt.subplot(beam(gridSize/2-plotSize/2,gridSize/2-plotSize,plotSize/2))
          ax2  = plt.subplot(beam(gridSize/2+plotSize/2,gridSize/2-plotSize,plotSize/2))
          ax9  = plt.subplot(beam(gridSize/2+3*plotSize/2,gridSize/2-plotSize,plotSize/2))
          ax12 = plt.subplot(beam(gridSize/2-3*plotSize/2,gridSize/2+plotSize,plotSize/2))
          ax5  = plt.subplot(beam(gridSize/2-plotSize/2,gridSize/2+plotSize,plotSize/2))
          ax4  = plt.subplot(beam(gridSize/2+plotSize/2,gridSize/2+plotSize,plotSize/2))
          ax10  = plt.subplot(beam(gridSize/2+3*plotSize/2,gridSize/2+plotSize,plotSize/2))
          ax8 = plt.subplot(beam(gridSize/2,gridSize/2-2*plotSize,plotSize/2))
          ax11 = plt.subplot(beam(gridSize/2,gridSize/2+2*plotSize,plotSize/2))
    
          axes = {
            "beam_01" : ax1,
            "beam_02" : ax2,
            "beam_03" : ax3,
            "beam_04" : ax4,
            "beam_05" : ax5,
            "beam_06" : ax6,
            "beam_07" : ax7,
            "beam_08" : ax8,
            "beam_09" : ax9,
            "beam_10" : ax10,
            "beam_11" : ax11,
            "beam_12" : ax12,
            "beam_13" : ax13        
          }
          
          xpols, ypols = {}, {}  
      
          for key in axes.keys():
            # Create xpol and ypol lines
            xpols[key], = axes[key].plot(np.cumsum(np.ones(numchans)),np.ones(numchans), color=xpol_color)
            ypols[key], = axes[key].plot(np.cumsum(np.ones(numchans)),np.ones(numchans), color=ypol_color)
        
            # Format plot
            dmax, dmin = 0, 2
            axes[key].set_ylim(dmin, dmax)
            axes[key].set_xlim(0,numchans)
            
            # Plot styling
            axes[key].get_xaxis().set_visible(True)
            axes[key].get_yaxis().set_visible(True)
            
            axes[key].set_yticklabels(["" for i in range(len(axes[key].get_yticks() ))])
            axes[key].set_xticklabels(["" for i in range(len(axes[key].get_xticks() ))])
            #axes["beam_08"].get_yaxis().set_visible(True)
            #axes["beam_09"].get_xaxis().set_visible(True)
            #axes["beam_10"].get_xaxis().set_visible(True)

          fig.canvas.draw()
          
          return fig, axes, xpols, ypols

    def createOverallPowerPlot(self, numchans=ntime, beamid='beam_01'):
          """ Creates an overall power vs time plot. """
          
          fig = plt.figure(figsize=(3,4),dpi=80)
          ax = plt.subplot(111)
          
          # Create 13 lines
          lines = []
          colors = [
              '#cd4a4a', '#ff6e4a', '#9f8170', '#ffcf48', '#bab86c', '#c5e384', '#1dacd6',
              '#71bc78', '#9aceeb', '#1a4876', '#9d81ba', '#cdc5c2', '#fc89ac'
              ]
           
          x, y = np.cumsum(np.ones(numchans))*2, np.ones(numchans) * 1e4
          for idx in range(13):
              line, = ax.plot(x, y, color=colors[idx], lw=1.5, label='%02da'%(idx+1))
              lines.append(line)
              
          for idx in range(13):
              line, = ax.plot(x, y, color=colors[idx], lw=1.5, label='%02db'%(idx+1), linestyle='--')
              lines.append(line)
        
          # Format plot
          ax.set_ylim(0, 2)
          ax.set_xlim(0,numchans*2)
          ax.set_xlabel("Elapsed Time (s)")
          ax.set_ylabel("Overall Power")

          # Shink current axis by 20%
          box = ax.get_position()
          ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])

          # Put a legend to the right of the current axis
          ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), ncol=2)
            
          fig.canvas.draw()
          
          return fig, ax, lines
    
    def updateOverallPowerPlot(self, key, xx, yy):
        """ Update power monitor plot. """
        
        key = int(key.lstrip("beam_")) -1
  
        g_max, g_min = self.p_lines[0].get_ydata().max(), self.p_lines[0].get_ydata().min()  
        for line in self.p_lines:
            l_max, l_min = line.get_ydata().max(), line.get_ydata().min()
            if l_max > g_max: g_max = l_max
            if l_min < g_min: g_min = l_min
        
        line_data_x, line_data_y = self.p_lines[key].get_ydata(), self.p_lines[key+13].get_ydata()
        line_data_x, line_data_y = np.roll(line_data_x, 1), np.roll(line_data_y, 1)
        line_data_x[0], line_data_y[0] = xx, yy
        self.p_lines[key].set_ydata(line_data_x), self.p_lines[key+13].set_ydata(line_data_y)
        self.p_ax.set_ylim(g_min/1.01, g_max*1.01)
    
    def updateTimeSeriesData(self, key, new_data):
        """ Update time series data for waterfall plot """
        self.time_series_data[key] = np.roll(self.time_series_data[key], -1, axis=0)
        self.time_series_data[key][0] = new_data
            
    def updateWaterfallPlot(self):
        """ Updates waterfall plot with new values """
        
        self.wf_data = self.time_series_data[self.activeBeam]
        self.wf_imshow.set_data(self.wf_data)

        new_data = self.time_series_data[self.activeBeam][0]        
        avg = np.average(new_data[20:-20])
        std = np.std(new_data[20:-20])
        thr = self.wf_thr
        ticks = np.linspace(avg - thr*std , avg + thr*std )
        
        self.wf_ax.set_title("Beam: %s"%self.activeBeam)
        #self.wf_colorbar.set_clim(avg - thr*std , avg + thr*std )
        self.wf_imshow.set_clim(avg - thr*std , avg + thr*std )
        #self.wf_colorbar.set_ticks(ticks, update_ticks = False)
        #self.wf_colorbar.update_ticks()
    
    def updateSingleBeamPlot(self, xx, yy):
        """ Updates single beam plot with new data """
        self.sb_xpol.set_ydata(xx)
        self.sb_ypol.set_ydata(yy)
        
        update_ax = False
        dmax, dmin = np.max([xx, yy]), np.min([xx, yy])
        if dmax > self.sb_max:
            update_ax = True
            self.sb_max = dmax
        if dmin < self.sb_min:
            update_ax = True 
            self.sb_min = dmin
        if update_ax:
             self.sb_ax.set_ylim(self.sb_min, self.sb_max)
             
        self.sb_fig.canvas.draw()
        
        
    def updateWaterfallThreshold(self):
        """ Change the threshold value for the waterfall plot """
        self.wf_thr = float(self.wf_line_edit.text())
        avg = np.average(self.wf_data[0][20:-20])
        std = np.std(self.wf_data[0][20:-20])
        self.wf_imshow.set_clim(avg - self.wf_thr*std , avg + self.wf_thr*std )
        self.wf_fig.canvas.draw()

    def updateAllPlots(self):
        """ Redraw all graphs in GUI when new data arrives """ 
        for elem in self.udpBuffer:
            data = json.loads(elem)
            
            #print data.keys()
            for key in data.keys():
                self.keyLookup(key, data)
        
        # Redraw plots            
        self.mb_fig.canvas.draw()
        
        self.p_fig.canvas.draw()
        self.wf_fig.canvas.draw()
        
        # Clear buffer
        self.udpCount = 0
        self.udpBuffer.clear()    





def main():
    print "Starting HIPSR User Interface..."
    app = QtGui.QApplication(sys.argv)
    gui = HipsrGui()
    app.exec_()
    sys.exit()    

if __name__ == '__main__':
    
    # Option parsing to allow command line arguments to be parsed
    p = OptionParser()
    p.set_usage('hipsr_gui.py [options]')
    p.set_description(__doc__)
    p.add_option("-i", "--hostip", dest="hostip", type="string", default="127.0.0.1",
                 help="change host IP address to run server. Default is localhost (127.0.0.1)")
    p.add_option("-p", "--hostport", dest="hostport", type="int", default=59012,
                 help="change host port for server. Default is 59012")
    p.add_option("-b", "--buffer", dest="buffer", type="int", default=8192,
                 help="change UDP buffer length. Default is 8192")

    (options, args) = p.parse_args(sys.argv[1:])

    main()
