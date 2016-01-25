### based on dockingexample.oxt by hanya
#(see https://forum.openoffice.org/en/forum/viewtopic.php?f=20&t=66391)
###
import uno
import unohelper
import ctypes




from com.sun.star.lang import XSingleComponentFactory, XServiceInfo
from com.sun.star.view import XSelectionChangeListener

from com.sun.star.task import XJobExecutor
from com.sun.star.awt import Rectangle, Size, WindowDescriptor, XActionListener, XFocusListener, XKeyListener, XTextListener, XWindowListener
from com.sun.star.awt.WindowClass import SIMPLE
from com.sun.star.awt.WindowAttribute import SHOW, BORDER, SIZEABLE, MOVEABLE, CLOSEABLE
from com.sun.star.awt.VclWindowPeerAttribute import CLIPCHILDREN
from com.sun.star.awt.PosSize import POS, SIZE
from com.sun.star.beans import NamedValue

# Implementation name should be match with name of
# the configuration node and FactoryImplementation value.
IMPLE_NAME = "tud.mci.tangram.Properties.DockingWindowFactory"
SERVICE_NAMES = (IMPLE_NAME,)
# Valid resource URL for docking window starts with
# private:resource/dockingwindow. And valid name for them are
 # 9800 - 9809 (only 10 docking windows can be created).
# See lcl_checkDockingWindowID function defined in
# source/sfx2/source/dialog/dockwin.cxx.
# If the name of dockingwindow conflict with other windows provided by
# other extensions, strange result would be happen.
RESOURCE_URL = "private:resource/dockingwindow/9809"

EXT_ID = "tud.mci.tangram.Properties.DockingWindow"


global no_selection_text
no_selection_text = "no shape selected"


class Factory(unohelper.Base, XSingleComponentFactory, XServiceInfo):

    def __init__(self, ctx):
        self.ctx = ctx

    # XSingleComponentFactory
    def createInstanceWithContext(self, ctx):
        # No way to get the parent frame, not called
        return self.createInstanceWithArgumentsAndContext(None, ctx)

    def createInstanceWithArgumentsAndContext(self, args, ctx):
        try:
            return create_dockable_window(ctx, args)
        except Exception as e:
            return None
    # XServiceInfo

    def supportedServiceNames(self):
        return SERVICE_NAMES

    def supportsService(self, name):
        return name in SERVICE_NAMES

    def getImplementationName(self):
        return IMPLE_NAME

strText = str(SERVICE_NAMES) + " " + str(IMPLE_NAME)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Factory, IMPLE_NAME, SERVICE_NAMES)


def create_dockable_window(ctx, args):
    """ Creates docking window.
        @param ctx component context
        @param args arguments passed by the window content factory manager.
        @return new docking window
    """
    def create(name):
        return ctx.getServiceManager().createInstanceWithContext(name, ctx)
    if not args:
        return None

    frame = None  # frame of parent document window
    for arg in args:
        name = arg.Name
        if name == "ResourceURL":
            if arg.Value != RESOURCE_URL:
                return None
        elif name == "Frame":
            frame = arg.Value

    if frame is None:
        return None  # ToDo: raise exception

    # this dialog has no title and is placed at the top left corner.
    dialog1 = "vnd.sun.star.extension://tud.mci.tangram.Properties.DockingWindow/TitleDescDialog.xdl"
    window = None
    if True:
        try:
            toolkit = create("com.sun.star.awt.Toolkit")
            parent = frame.getContainerWindow()

            # Creates outer window (title name of this window is defined in WindowState configuration)
            desc = WindowDescriptor(SIMPLE, "window", parent, 0, Rectangle(0, 0, 100, 120), SHOW | SIZEABLE | MOVEABLE | CLOSEABLE | CLIPCHILDREN)
            window = toolkit.createWindow(desc)

            # Create inner window from dialog
            dp = create("com.sun.star.awt.ContainerWindowProvider")
            child = dp.createContainerWindow(dialog1, "", window, None)
            child.setVisible(True)
            child.setPosSize(0, 0, 0, 0, POS)  # if the dialog is not placed at top left corner

            window.addWindowListener(WindowResizeListener(child, window))

            controller = frame.getController()
            controller.addSelectionChangeListener(SelectionChangeListener(child, controller))

            tf_title = child.getControl("TextField_Title")
            listener1 = EditListener(1, controller, tf_title, child)
            tf_title.addKeyListener(listener1)
            tf_title.addFocusListener(listener1)
            tf_title.addTextListener(listener1)
            no_selection_text = tf_title.getText()

            tf_desc = child.getControl("TextField_Desc")
            listener2 = EditListener(2, controller, tf_desc, child)
            tf_desc.addKeyListener(listener2)
            tf_desc.addFocusListener(listener2)
            tf_desc.addTextListener(listener2)

            btn_save = child.getControl("CommandButton_Save")
            listener3 = ButtonListener(3, controller, child)
            btn_save.addActionListener(listener3)

            tf_title.setEnable(False)
            tf_desc.setEnable(False)
            btn_save.setEnable(False)
            tf_title.setText(str(no_selection_text))
            tf_desc.setText(str(no_selection_text))

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "dialog add error", 1)

    return window


class SelectionChangeListener(unohelper.Base, XSelectionChangeListener):
    def __init__(self, parent, s_supplier):
        self.parent = parent
        self.controller = s_supplier
        self.multi_selection = False

    def disposing(self, ev):
        self.parent = None

    def selectionChanged(self, ev):
        selection = self.controller.getSelection()
        if selection:
            if selection.getCount() > 1:
                self.multi_selection = True
            else:
                self.multi_selection = False
            self.enable_fields(True, self.parent)
            self.fill_values(selection, self.parent)
        else:
            self.multi_selection = False
            self.enable_fields(False, self.parent)
            self.fill_values(selection, self.parent)
        self.parent.selection_changed(ev) # macht das überhaupt was? parent sollte quasi das Fenster sein... evtl. super.selection_changed(ev), um es in Elternklasse aufzurufen?

    def fill_values(self, selection, dialog):
        try:
            if selection:
                shape = selection.getByIndex(0)
                title = shape.getPropertyValue("Title")
                desc = shape.getPropertyValue("Description")
                dialog.getControl("TextField_Title").setText(title)
                dialog.getControl("TextField_Desc").setText(desc)
            else:
                dialog.getControl("TextField_Title").setText(str(no_selection_text))
                dialog.getControl("TextField_Desc").setText(str(no_selection_text))
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "fill values error", 1)

    def enable_fields(self, enabled, dialog):
        try:
            dialog.getControl("TextField_Title").setEnable(enabled)
            dialog.getControl("TextField_Desc").setEnable(enabled)
            dialog.getControl("CommandButton_Save").setEnable(self.multi_selection)
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "enable fields error", 1)


class ButtonListener(unohelper.Base, XActionListener):

    def __init__(self, kind, controller, dialog):
        self.kind = kind
        self.controller = controller
        self.btn_save = dialog.getControl("CommandButton_Save")
        self.tf_title = dialog.getControl("TextField_Title")
        self.tf_desc = dialog.getControl("TextField_Desc")

    def disposing(self, ev):
        pass

    # XActionListener
    def actionPerformed(self, ev):
        try:
            title = self.tf_title.getText()
            desc = self.tf_desc.getText()
            selection = self.controller.getSelection()
            count = selection.getCount()
            i = 0
            for i in range(0, count):
                shape = selection.getByIndex(i)
                shape.setPropertyValue("Title", title)
                shape.setPropertyValue("Description", desc)
            self.btn_save.setEnable(False)
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "button listener error", 1)


class EditListener(unohelper.Base, XKeyListener, XFocusListener, XTextListener):

    def __init__(self, kind, controller, dialog_control, dialog):
        self.kind = kind
        self.applied = False
        self.controller = controller
        self.dialog_control = dialog_control
        self.dialog = dialog

    def apply(self):
        self.applied = True

        try:
            selection = self.controller.getSelection()
            shape = selection.getByIndex(0)

            if self.kind & 1:
                title = shape.getPropertyValue("Title")
                _title = self.dialog_control.getText()
                if title != _title:
                    title = _title
                    shape.setPropertyValue("Title", title)

            if self.kind & 2:
                desc = shape.getPropertyValue("Description")
                _desc = self.dialog_control.getText()
                if desc != _desc:
                    desc = _desc
                    shape.setPropertyValue("Description", desc)

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "apply error", 1)

    def disposing(self, ev):
        self.parent = None

    def focusGained(self, ev):
        pass

    def focusLost(self, ev):
        if not self.applied:
            self.apply()
            self.applied = True

    def keyPressed(self, ev):
        pass

    def keyReleased(self, ev):
        pass

    def textChanged(self, ev):
        self.applied = False

        # enable save-button
        selection = self.controller.getSelection()
        if selection.getCount() > 1:
            self.dialog.getControl("CommandButton_Save").setEnable(True)


class WindowResizeListener(unohelper.Base, XWindowListener):

    def __init__(self, dialog, window):
        self.dialog = dialog
        self.window = window

    def disposing(self, ev):
        pass

    # XWindowListener
    def windowMoved(self, ev):
        pass

    def windowShown(self, ev):
        pass

    def windowHidden(self, ev):
        pass

    def windowResized(self, ev):
        min_size = Size(150, 240)
        try:
            # extends inner window to match with the outer window
            if self.dialog:
                if (ev.Width >= min_size.Width) and (ev.Height >= min_size.Height):
                    self.dialog.setPosSize(0, 0, ev.Width, ev.Height, SIZE)

                    # resize dialog elements
                    tf_title = self.dialog.getControl("TextField_Title")
                    tf_title_height = tf_title.getPosSize().Height
                    tf_title.setPosSize(0, 0, ev.Width-20, tf_title_height, SIZE)
                    tf_desc = self.dialog.getControl("TextField_Desc")
                    tf_desc_height = tf_desc.getPosSize().Height
                    tf_desc.setPosSize(0, 0, ev.Width-20, tf_desc_height, SIZE)

                else:  # ToDo: no resize if minimum size is reached
                    pass

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxA(0, str(e), "window resize error", 1) 




