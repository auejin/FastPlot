# FastPlot

<img src="fastplot.gif" alt="fastplot" style="width:50%;" />

This renders a real-time matplotlib plot using data from serial input streams. You can click the plot to pause updates, or close the window to terminate logging threads. This assumes each row is formatted as `<var0><delim>...<delim><varN>`. If not, you can modify the input stream with your own filter before parsing.



## Install

```bash
pip install -r requirements.txt
```



## How to Use

### LinePlotter

```python
import fastplot as pp
import matplotlib.pyplot as plt

# specify a serial port to read
board = pp.Poller()
board.connect('COM11', 115200)
board.start()

# draw a line plot (like a serial plot of Arduino IDE)
canvas = pp.LinePlotter(
	labels=['col_a', 'col_b', 'col_c'],
    poller=board, rows=100, )

# define plot parameters
anim = canvas.draw(interval=10)
plt.show()
```



### BarPlotter

```python
import fastplot as pp
import matplotlib.pyplot as plt

# specify a serial port to read
board = pp.Poller()
board.connect('COM11', 115200)
board.start()

# draw a bar plot (visualize only the most recent row)
canvas = pp.BarPlotter(
	labels=['col_a', 'col_b', 'col_c'],
    poller=board, )

# define plot parameters
anim = canvas.draw(interval=10)
plt.show()
```



### Preprocessing Input Stream

```python
import fastplot as pp
import matplotlib.pyplot as plt

# define a preprocessing function from serial input
f = lambda x: x.replace('Quaternion:','').replace('nan','0.0')

# specify a serial port to read
board = pp.Poller(filter=f)
board.connect('COM11', 115200)
board.start()

# draw a bar plot (visualize only the most recent row)
canvas = pp.BarPlotter(
	labels=['col_a', 'col_b', 'col_c'],
    poller=board, )

# define plot parameters
anim = canvas.draw(interval=10)
plt.show()
```

