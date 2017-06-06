from IPython.html.widgets import FloatProgressWidget
from IPython.display import display

def display_progress(collection):
  """
    >>> l = [1,2,3]
    >>> for e in display_progress(l): do_something(e)
  """
  f = FloatProgressWidget(min=0, max=len(collection))
  display(f)
  for element in collection:
    f.value += 1
    yield element