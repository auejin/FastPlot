import serial
import serial.tools.list_ports
from threading import Thread

import matplotlib.pyplot as plt
import matplotlib.animation as animation

class BlitManager:
    def __init__(self, canvas, animated_artists=()):
        """
        This entire class is from [the official matplotlib doc](https://matplotlib.org/stable/tutorials/advanced/blitting.html#class-based-example).

        Parameters
        ----------
        canvas : FigureCanvasAgg
            The canvas to work with, this only works for sub-classes of the Agg
            canvas which have the `~FigureCanvasAgg.copy_from_bbox` and
            `~FigureCanvasAgg.restore_region` methods.

        animated_artists : Iterable[Artist]
            List of the artists to manage
        """
        self.canvas = canvas
        self._bg = None
        self._artists = []

        for a in animated_artists:
            self.add_artist(a)
        # grab the background on every draw
        self.cid = canvas.mpl_connect("draw_event", self.on_draw)

    def on_draw(self, event):
        """Callback to register with 'draw_event'."""
        cv = self.canvas
        if event is not None:
            if event.canvas != cv:
                raise RuntimeError
        self._bg = cv.copy_from_bbox(cv.figure.bbox)
        self._draw_animated()

    def add_artist(self, art):
        """
        Add an artist to be managed.

        Parameters
        ----------
        art : Artist

            The artist to be added.  Will be set to 'animated' (just
            to be safe).  *art* must be in the figure associated with
            the canvas this class is managing.

        """
        if art.figure != self.canvas.figure:
            raise RuntimeError
        art.set_animated(True)
        self._artists.append(art)

    def _draw_animated(self):
        """Draw all of the animated artists."""
        fig = self.canvas.figure
        for a in self._artists:
            fig.draw_artist(a)

    def update(self):
        """Update the screen with animated artists."""
        cv = self.canvas
        fig = cv.figure
        # paranoia in case we missed the draw event,
        if self._bg is None:
            self.on_draw(None)
        else:
            # restore the background
            cv.restore_region(self._bg)
            # draw all of the animated artists
            self._draw_animated()
            # update the GUI state
            cv.blit(fig.bbox)
        # let the GUI event loop process anything it has to do
        cv.flush_events()

class Poller:
    def __init__(self, filter=None):
        """ after initialization, you must `connect()` to your serial port and `start()` receiving data.
        
        Args:
            filter (lambda) : a string filter before splitting with delimiter.
        """

        self.thread = None
        self.serial = None
        self.runing = False
        self.rows = []
        
        self.filter = filter

    def start(self):
        """ set `self.running` as `True` and start updating `self.rows` """
        self.running = True
        self.thread = Thread(target=self._thr_read)
        self.thread.start()
    
    def close(self):
        """ set `self.running` as `False` and stop updating `self.rows` """
        self.running = False
        self.thread.join()

    def _thr_read(self):
        while self.running and self.serial.is_open:
            data = self.serial.readline().decode().strip()
            if len(data) > 0:
                if self.filter is not None and callable(self.filter) :
                    data = f(data)
                self.rows.append(data)

    def connect(self, keyword:str, baud:int):
        """ connect to a serial port filtered by given `keyword`
        
        Args:
            keyword (str) : name of serial plot to record
            baud (int) : baudrate of serial plot
        """
        ports = list(serial.tools.list_ports.comports())
        ser = serial.Serial()

        if len(ports) < 1 :
            raise Exception('no serial port is available')
        else:
            port_to_connect = ''
            
            for port, name, pid in ports:
                if keyword in name:
                    print(f'connecting to `{name}` ...', end=' ')
                    port_to_connect = port
                    break
            
            if port_to_connect == '':
                print(f'no port name including `{keyword}` found.')
                return
            
            else:
                ser.port = port_to_connect
                ser.barudrate = baud
                ser.timeout = 10
                ser.open()

                if ser.is_open:
                    print('connected.')
                else:
                    print('connection failed.')
        
        self.serial = ser

class LinePlotter:
    def __init__(self, labels, poller:Poller, rows:int=30, delim:str=','):
        """ A real-time line graph plotter from serial input.
        This assumes each row is formatted as `<var0><delim>...<delim><varN>`.

        You can click the plot to pause updates, or close the window to terminate logging threads.
        
        Args: 
            labels (int) : varaibles to plot
            rows (int) : number of rows to visualize
            delim (str) : delimiter character to separate each variable
        """

        self.poller = poller

        # data vis
        self.fig, self.ax = plt.subplots(1, 1, figsize=(10,5))
        self.fig.canvas.mpl_connect('button_press_event', self._click_to_pause)
        self.fig.canvas.mpl_connect('close_event', self._finish_when_closed)
        self.paused = False

        # data trim
        self.delim = delim
        self.row_idx = 0
        self.row_max = rows
        
        # init data to visualize
        self.labels = labels
        self.lines = {}
        self.d = {'x':[0]*self.row_max}
        for label in self.labels:
            self.d[label] = [0]*self.row_max
            (line,) = self.ax.plot(self.d['x'], self.d[label], animated=True, label=label)
            self.lines[label] = line
        
        # finalize size and location of plot and legend
        self.ax.legend(
            handles=self.lines.values(), frameon=False, 
            bbox_to_anchor=(0.5, -0.2), loc='lower center', 
            borderaxespad=0., ncol=len(self.lines))
        plt.tight_layout()

        # this enables fast rendering for matplotlib
        self.bm = BlitManager(self.fig.canvas, self.lines.values())
        plt.show(block=False)
        plt.pause(.1)
    
    def _finish_when_closed(self, event):
        """ gracefully shut down the process when plot window is closed """
        self.poller.close()
        plt.close('all')

    def _click_to_pause(self, event):
        """ click to pause or resume real-time plotting """
        self.paused = not self.paused

    def push(self, frame:int):
        """ append a string of row received from serial port
        
        Args:
            frame (int) : number of frame to be rendered
        """

        if not self.poller.running:
            return

        # read from poller
        rows = self.poller.rows
        
        for row in rows:
            # render when unread row exists and graph is not paused
            if len(row) == 0:
                continue
            
            # row string to row list
            row = list(map(float, row.split(self.delim)))

            # update x
            self.d['x'].pop(0)
            self.d['x'].append(self.row_idx)

            # update labels
            for i, label in enumerate(self.labels):
                if i >= len(row):
                    break
                self.d[label].pop(0)
                self.d[label].append(row[i])
                # print(label, self.d[label][-5:])
                
                if not self.paused:
                    self.lines[label].set_xdata(self.d['x'])
                    self.lines[label].set_ydata(self.d[label])
            
            if not self.paused:
                ymax = max([max(self.d[label]) for label in self.labels])
                ymin = min([min(self.d[label]) for label in self.labels])
                ymargin = 0.05 * (ymax - ymin)
                if ymargin > 0:
                    self.ax.set_ylim([ymin - ymargin, ymax + ymargin])
                if self.d['x'][0] != self.d['x'][-1]:
                    self.ax.set_xlim([self.d['x'][0], self.d['x'][-1]])
                self.bm.update()

            self.row_idx += 1
        
        # empty buffer
        self.poller.rows = []
    
    def draw(self, interval:int):
        """ append a `row` over the plot after a given `interval` (ms) """
        anim = animation.FuncAnimation(self.fig, self.push, frames=None, fargs=None, interval=interval)
        return anim

class BarPlotter:
    def __init__(self, labels, poller:Poller, delim:str=','):
        """ A real-time bar graph plotter from serial input.
        This assumes each row is formatted as `<var0><delim>...<delim><varN>`.

        You can click the plot to pause updates, or close the window to terminate logging threads.
        
        Args: 
            labels (int) : varaibles to plot
            delim (str) : delimiter character to separate each variable
        """

        self.poller = poller

        # data vis
        self.fig, self.ax = plt.subplots(1, 1, figsize=(10,5))
        self.fig.canvas.mpl_connect('button_press_event', self._click_to_pause)
        self.fig.canvas.mpl_connect('close_event', self._finish_when_closed)
        self.paused = False

        # data trim
        self.delim = delim
        
        # init data to visualize
        self.labels = labels
        self.bars = self.ax.bar(labels, [0]*len(labels))
        plt.tight_layout()

        # this enables fast rendering for matplotlib
        self.bm = BlitManager(self.fig.canvas, self.bars)
        plt.show(block=False)
        plt.pause(.1)
    
    def _finish_when_closed(self, event):
        """ gracefully shut down the process when plot window is closed """
        self.poller.close()
        plt.close('all')

    def _click_to_pause(self, event):
        """ click to pause or resume real-time plotting """
        self.paused = not self.paused

    def push(self, frame:int):
        """ append a string of row received from serial port
        
        Args:
            frame (int) : number of frame to be rendered
        """

        if not self.poller.running:
            return

        # read from poller
        rows = self.poller.rows
        
        for row in rows:
            # render when unread row exists and graph is not paused
            if len(row) == 0:
                continue
            
            # row string to row list
            row = list(map(float, row.split(self.delim)))

            # update labels
            for i, label in enumerate(self.labels):
                if i >= len(row):
                    break
                if not self.paused:
                    self.bars[i].set_height(row[i])
            
            if not self.paused:
                ymax, ymin = max(row), min(row)
                ymargin = 0.05 * (ymax - ymin)
                if ymargin > 0:
                    self.ax.set_ylim([ymin - ymargin, ymax + ymargin])
                self.bm.update()
        
        # empty buffer
        self.poller.rows = []
    
    def draw(self, interval:int):
        """ append a `row` over the plot after a given `interval` (ms) """
        anim = animation.FuncAnimation(self.fig, self.push, frames=None, fargs=None, interval=interval)
        return anim

if __name__ == '__main__' :
    
    # an arbitrary preprocessing function from serial input
    f = lambda x: x.replace('Quaternion:','').replace('nan','0.0')

    board = Poller(filter=f)
    board.connect('COM11', 115200)
    board.start()

    
    plotter = LinePlotter(labels=['data_a', 'data_b', 'data_c', 'data_d'], poller=board, rows=100)
    # plotter = BarPlotter(labels=['data_a', 'data_b', 'data_c', 'data_d'], poller=board)
    anim = plotter.draw(10)
    plt.show()
