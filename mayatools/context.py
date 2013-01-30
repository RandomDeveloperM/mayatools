"""Context managers for Maya state."""

import contextlib
import functools

from uitools.qt import QtGui

from maya import cmds, mel


@contextlib.contextmanager
def attrs(*args, **kwargs):
    """Change some attributes, and reset them when leaving the context.
    
    :param args: Mappings of attributes to values.
    :param kwargs: More attributes and values.
    :returns: A dictionary of the original values will be bound to the target of
        the with statement. Changed to that dictionary will be applied.
    
    Useful for playblasting::
    
        >>> with mayatools.context.attrs({'defaultRenderGlobals.imageFormat': 8}):
        ...     # Playblast with confidence that the render globals will be reset.
    
    """
    
    # Collect all the arguments.
    for arg in args:
        kwargs.update(arg)
    
    existing = {}
    try:
        
        # Set all of the requested attributes.
        for name, value in kwargs.iteritems():
            existing[name] = cmds.getAttr(name)
            cmds.setAttr(name, value)
        
        yield existing
    
    finally:
        
        # Reset them back to normal.
        for name, value in existing.iteritems():
            cmds.setAttr(name, value)


def command(func, *args, **kwargs):
    """A context manager that uses the standard query interface.
    
    Pass any values via keyword arguments and their original values will be
    saved via ``func(*args, query=True, yourAttribute=True)``, and finally
    restored via ``func(*args, yourAttribute=original)`` or
    ``func(*args, edit=True, yourAttribute=original)`` if you also specify
    ``edit=True``.
    
    :param func: A callable, or name of a Maya command.
    :param args: Positional arguments for the given ``func``.
    :param kwargs: Values to set within the context. ``edit`` is special and
        marks if values should be set with an ``edit`` flag or not.
    
    A dictionary of the original values will be bound to the target of the with
    statement. Changed to that dictionary will be applied.
    
    If you are already using a query pattern like::
    
        >>> current_time_unit = cmds.currentUnit(time)
        >>> cmds.currentUnit(time='film')
        >>> 
        >>> try:
        ...     # Do something.
        ... finally:
        ...     cmds.currentUnit(time=current_time_unit)
    
    then you can use this manager directly::
    
        >>> with command(cmds.currentUnit, time='film') as originals:
        ...     # Do something.
    
    or as a context manager factory::
    
        >>> currentUnit = command(cmds.currentUnit)
        >>> with currentUnit(time='film') as originals:
        ...     # Do something.
    
    If your command requires the ``edit`` keyword, pass it to this function::
    
        >>> with ctx.command(cmds.camera, my_camera, edit=True, overscan=1):
        ...     # Do something with the camera.
    
    """
    if args or kwargs:
        return _command(func, *args, **kwargs)
    else:
        return functools.partial(_command, func)


@contextlib.contextmanager
def _command(func, *args, **kwargs):
        
    if isinstance(func, basestring):
        func = getattr(cmds, func)
    
    edit = bool(kwargs.pop('edit', None))
    
    existing = {}
    try:
            
        # Set the requested parameters.
        for name, value in kwargs.iteritems():
            existing[name] = func(*args, query=True, **{name: True})
            if edit:
                func(*args, edit=True, **{name: value})
            else:
                func(*args, **{name: value})
            
        yield existing
        
    finally:
            
        # Reset them back to normal.
        for name, value in existing.iteritems():
            if edit:
                func(*args, edit=True, **{name: value})
            else:
                func(*args, **{name: value})
    

@contextlib.contextmanager
def selection(*args, **kwargs):
    """A context manager that resets selections after exiting.

    :param args: Passed to ``cmds.select``.
    :param kwargs: Passed to ``cmds.select``.
    
    A list of the original selection will be bound to the target of the with
    statement. Changes to that list will be applied.
    
    Example::
    
        >>> with selection(clear=True):
        ...     # Do something with an empty selection.
    
    """
    existing = cmds.ls(selection=True) or []
    try:
        if args or kwargs:
            cmds.select(*args, **kwargs)
        yield existing
    finally:
        if existing:
            cmds.select(existing, replace=True)
        else:
            cmds.select(clear=True)
    

_suspend_depth = 0

@contextlib.contextmanager
def suspend_refresh():
    """A context mananger that stops the graph from running or the view
    updating.

    Can be nested, where only the outermost context manager will resume
    refresing.

    .. seealso::

        There are caveats with disabling the refresh cycle. Be sure to 
        read about :cmds:`refresh`.

    """

    global _suspend_depth
    try:
        if not _suspend_depth:
            cmds.refresh(suspend=True)
        _suspend_depth += 1
        yield
    finally:
        _suspend_depth -= 1
        if not _suspend_depth:
            cmds.refresh(suspend=False)



class progress(object):
    """A context manager to assist with the global progress bar.

    Since your code is running in the main thread, this is not actually
    cancellable by the user since keyboard events will not be caught.

    ::

        with progress("Testing", max=100) as p:
            for i in range(100):
                time.sleep(0.02)
                p.update(i, 'Testing %d of 100' % (i + 1))

    .. warning:: This API is subject to fluctuation as we attempt to figure
        out something that will not pause the event loop.
    
    """

    def __init__(self, status, max=100, min=0):
        self._status = status
        self._min = min
        self._max = max

    def step(self, size=1):
        cmds.progressBar(self._bar, edit=True, step=size)

    def update(self, value=None, status=None, min=None, max=None):
        self._status = status or self._status
        self._min = min or self._min
        self._max = max or self._max
        kwargs = {'progress': value} if value is not None else {}
        cmds.progressBar(self._bar, edit=True,
            status=self._status,
            minValue=self._min,
            maxValue=self._max,
            **kwargs
        )

    def _show(self):
        main_bar = mel.eval('$tmp = $gMainProgressBar')
        self._bar = cmds.progressBar(main_bar,
            edit=True,
            beginProgress=True,
            status=self._status,
            minValue=self._min,
            maxValue=self._max,
        )

    def _hide(self):
        cmds.progressBar(self._bar, edit=True, endProgress=True)

    def __enter__(self):
        self._show()
        return self

    def __exit__(self, *args):
        self._hide()



