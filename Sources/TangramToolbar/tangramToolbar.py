# -*- coding: utf-8 -*-

import unohelper
import uno
import ctypes
import subprocess
import os, sys, string
from array import array
#import java.lang.Object.util.DrawTools --> wie komm ich da ran?

from com.sun.star.beans import (PropertyChangeEvent, XPropertyChangeListener, XPropertySet, PropertyValue, UnknownPropertyException)
from com.sun.star.beans.PropertyAttribute import OPTIONAL

from com.sun.star.frame import (FeatureStateEvent, XControlNotificationListener, 
    XDispatch, XDispatchProvider, XStatusListener, XToolbarController, XSubToolbarController)
from com.sun.star.lang import (XEventListener, XInitialization, XServiceInfo, WrappedTargetException)
from com.sun.star.view import XSelectionChangeListener
from com.sun.star.document import XUndoAction

from com.sun.star.awt import (Rectangle, WindowDescriptor, XItemList, XItemListener, XSpinListener, 
    XKeyListener, XFocusListener, XTextListener, XWindowListener, XActionListener)
from com.sun.star.awt.Key import RETURN
from com.sun.star.awt.WindowClass import SIMPLE, TOP
from com.sun.star.awt.WindowAttribute import SHOW, SIZEABLE, MOVEABLE, CLOSEABLE
from com.sun.star.awt.VclWindowPeerAttribute import CLIPCHILDREN, DROPDOWN, RIGHT, SPIN
from com.sun.star.awt.PosSize import POS, SIZE

from com.sun.star.drawing import LineDash
from com.sun.star.drawing.LineStyle import SOLID as SolidLine
from com.sun.star.drawing.LineStyle import DASH as DashedLine
from com.sun.star.drawing.FillStyle import NONE, BITMAP, SOLID
from com.sun.star.drawing.TextVerticalAdjust import CENTER as TextVerticalCenter
from com.sun.star.drawing.TextHorizontalAdjust import LEFT as TextHorizontalLeft

from com.sun.star.view.DocumentZoomType import BY_VALUE


### based on PosSizeToolbar-alpha-0.1.0 extension from OpenOffice Forum ###


IMPL_NAME = "tud.mci.tangram.Properties"
IMPL_NAME2 = "tud.mci.tangram.PropertiesHandler"

# spacing (in 1/100 mm) which should be added to a line (1/2 of this on the one side, 1/2 on the other side of the border)
line_spacing = 400

# TODO get system language
language = "de"

# language definitions
warning = "Achtung"
no_selection = "Bitte wählen Sie ein Element aus."
to_much_selection = "Sie haben zu viele Elemente ausgewählt. Bitte selektieren Sie nur ein Element."


###############################################################################################################
###   event listener                                                                                        ###
###############################################################################################################

### listener for numeric fields ###
class NumericFieldListener(unohelper.Base, XKeyListener, XFocusListener, XSpinListener, XTextListener):
    def __init__(self, parent, kind):
        self.parent = parent
        self.kind = kind
        self.applied = False
    
    def apply(self):
        self.applied = True
        self.parent.apply(self.kind)
    
    def disposing(self, ev):
        self.parent = None
    
    def focusGained(self, ev): pass
    def focusLost(self, ev):
        if not self.applied:
            self.apply()
        self.applied = True
    
    def up(self, ev):
        self.apply()
    def down(self, ev):
        self.apply()
    def first(self, ev): pass
    def last(self, ev): pass
    
    def keyPressed(self, ev): pass
    def keyReleased(self, ev):
        if ev.KeyCode == RETURN:
            self.apply()
    
    def textChanged(self, ev):
        self.applied = False
    
### listener for edit fields ###    
##class EditListener(unohelper.Base, XKeyListener, XFocusListener, XTextListener):
##  def __init__(self, parent, kind):
##      self.parent = parent
##      self.kind = kind
##      self.applied = False
##  
##  def apply(self):
##      self.applied = True
##      self.parent.apply(self.kind)
##  
##  def disposing(self, ev):
##      self.parent = None
##  
##  def focusGained(self, ev): pass
##  def focusLost(self, ev):
##      if not self.applied:
##          self.apply()
##      self.applied = True
##  
##  def keyPressed(self, ev): pass
##  def keyReleased(self, ev):
##      if ev.KeyCode == RETURN:
##          self.apply()
##  
##  def textChanged(self, ev):
##      self.applied = False

### listener for list with measuring units ###
class UnitListListener(unohelper.Base, XItemListener):
    def __init__(self, parent):
        self.parent = parent
        
    def disposing(self, ev):
        self.parent = None
    
    def itemStateChanged(self, ev):
        self.parent.current_unit = self.parent.get_unit()       
        if ev.Selected == self.parent.PERCENT:
            self.parent.fill_values(None, size_only=True)
        else:
            self.parent.fill_values(None)

### listener for list with filling patterns ###
class PatternListListener(unohelper.Base, XItemListener):
    def __init__(self, parent):
        self.parent = parent
        
    def disposing(self, ev):
        self.parent = None
    
    def itemStateChanged(self, ev):
        self.parent.current_pattern = ev.Selected        
        self.parent.apply_pattern(self.parent.current_pattern)

### listener for list with line styles ###        
class LineListListener(unohelper.Base, XItemListener):
    def __init__(self, parent):
        self.parent = parent
        
    def disposing(self, ev):
        self.parent = None
    
    def itemStateChanged(self, ev):
        self.parent.current_linestyle = ev.Selected        
        self.parent.apply_linestyle(self.parent.current_linestyle)

### listener for selection changes ###
class SelectionChangeListener(unohelper.Base, XSelectionChangeListener):
    def __init__(self, parent):
        self.parent = parent
    
    def disposing(self, ev):
        self.parent = None
    
    def selectionChanged(self, ev):
        self.parent.selection_changed(ev)

### listener for changes of the shape's properties ###
class PropertyChangeListener(unohelper.Base, XPropertyChangeListener):
    def __init__(self, parent):
        self.parent = parent
    
    def disposing(self, ev):
        self.parent = None
    
    def propertyChange(self, ev):
        self.parent.property_change(ev)


###############################################################################################################
###   Toolbar buttons                                                                                       ###
###############################################################################################################

### toggles the keep ratio property for changing the size of a shape ###        
class KeepRatioToggle(unohelper.Base, XDispatch, XControlNotificationListener):
    def __init__(self):
        self.state = False
        self.listener = None
    
    def get_state(self):
        return self.state
    
    def dispatch(self, url, args):
        self.state = not self.state
        ev = self.create_simple_event(url, self.state)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, state, enabled=True):
        return FeatureStateEvent(self, url, "", enabled, False, state)


### shows or hides the title and description edit fields in a separate docking window ###
class TitleDescToggle(unohelper.Base, XDispatch, XControlNotificationListener):
    def __init__(self, frames):
        self.listener = None
        self.frames = frames
        self.state = False # TODO: check if already open or not: self.check_docking_window_state()
    
    def get_state(self):
        return self.state
    
    def dispatch(self, url, args):
        self.state = not self.state
        ev = self.create_simple_event(url)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, enabled=True):
        state = self.switch_docking_window()
        return FeatureStateEvent(self, url, "", enabled, False, state)

    def switch_docking_window(self):  
        resource_url = "private:resource/dockingwindow/9809"
        try:
            controller = get_controller(self.frames)
            if not controller:
                return
            frame = controller.getFrame()
            if not frame:
                return
            layout_manager = frame.LayoutManager
            if not layout_manager:
                return
            
            if layout_manager.isElementVisible(resource_url):
                layout_manager.hideElement(resource_url)
                return False
            else:
                layout_manager.requestElement(resource_url)
                return True
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "switch docking window error", 1)

##    def check_docking_window_state(self):
##        resource_url = "private:resource/dockingwindow/9809"
##        try:
##            controller = get_controller(self.frames)
##            layout_manager = controller.getFrame().LayoutManager # scheinbar hat controller noch keinen Frame beim init
##            if layout_manager.isElementVisible(resource_url):
##                return true
##            else:
##                return false
##        except Exception as e:
##            print(e)
##            ctypes.windll.user32.MessageBoxW(0, str(e), "check docking window", 1)


### opens the tool for checking the graphic against some guidelines ###
class OpenCheckTool(unohelper.Base, XDispatch, XControlNotificationListener):
    def __init__(self):
        self.state = False
        self.listener = None
    
    def get_state(self):
        return self.state
    
    def dispatch(self, url, args):
        #self.state = not self.state
        ev = self.create_simple_event(url, self.state)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, state, enabled=True):
        self.open_check_tool_window()
        return FeatureStateEvent(self, url, "", enabled, False, state)

    def open_check_tool_window(self):
        try:
            file_path = os.path.dirname(__file__)
            file_path = file_path.decode("utf-8")
            resource_url = os.path.join(file_path, 'QS-Dialog\QS-Dialog.exe')
            os.startfile(resource_url)
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "open check tool error", 1)


### Opens Tangram workstation for pin device support. Also sets zoom level to 100 percent and default styles to these based on Tangram guidelines. ###
class OpenTangramWorkstation(unohelper.Base, XDispatch, XControlNotificationListener):
    def __init__(self, ctx, frames):
        self.state = False
        self.listener = None
        self.ctx = ctx
        self.frames = frames
    
    def get_state(self):
        return self.state
    
    def dispatch(self, url, args):
        #self.state = not self.state
        ev = self.create_simple_event(url, self.state)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, state, enabled=True):
        #self.open_template()
        self.set_default_styles()
        self.start_lector_app()
        #self.set_bitmaps()
        return FeatureStateEvent(self, url, "", enabled, False, state)

    ### open Tangram template in a new window ###
    def open_template(self):
        try:
            file_path = os.path.dirname(__file__)
            file_path = file_path.decode("utf-8") 
            resource_url = os.path.join(file_path, 'TactileGraphic_Template_Landscape.otg')  
                       
            os.startfile(resource_url)
            # Problem: Title+Desc docking window is sometimes not opened in the new document #
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "open template error", 1)

    ### set default style of line and fill properties as well as the default font of the document to some values that base on Tangram guidelines ###
    def set_default_styles(self):
        try:
            desktop = self.ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            oDoc = desktop.getCurrentComponent()
            defaultStyle = oDoc.getStyleFamilies().getByName("graphics").getByName("standard")
            #ctypes.windll.user32.MessageBoxW(0, str(defaultStyle.getPropertySetInfo().getProperties()), "styles", 1)

            # ändert auch alle bisher erstellten Formen, die auf dem Standardtemplate basieren
            defaultStyle.LineStyle = SolidLine
            defaultStyle.LineColor = 0 # black --> integer color value = R + G*(256) + B*(256^2) #
            defaultStyle.LineWidth = 100 # 0,10 cm #
            defaultStyle.FillStyle = SOLID
            defaultStyle.FillColor = 0 # black
            
            # set default font #
            defaultStyle.CharFontName = "Braille DE Computer ASCII"
            defaultStyle.CharHeight = 40
            
            # set default text adjustment and distance to border #
            defaultStyle.TextLeftDistance = 300
            defaultStyle.TextRightDistance = 300
            defaultStyle.TextUpperDistance = 300
            defaultStyle.TextLowerDistance = 150
            defaultStyle.TextVerticalAdjust = TextVerticalCenter
            defaultStyle.TextHorizontalAdjust = TextHorizontalLeft
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "set default styles error", 1)   
    
    ### start Tangram lector application and set the zoom level of the document to 100 percent ###
    def start_lector_app(self):
        try:
            file_path = os.path.dirname(__file__)
            file_path = file_path.decode("utf-8") 
            resource_url = os.path.join(file_path, 'TangramLector\TangramLector.exe')           
            os.startfile(resource_url)
            self.set_document_zoom_level(100)
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "start lector app error", 1)
    
    ### set zoom level of the document to the given zoom level ###
    def set_document_zoom_level(self, zoomlevel):
        try:
            desktop = self.ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            oDoc = desktop.getCurrentComponent()
            controller = oDoc.getCurrentController()
            controller.ZoomType = BY_VALUE
            controller.ZoomValue = 100
            # TODO: offset verschieben (ganz links oben)
            #controller.ViewOffset.X = 0
            #controller.ViewOffset.Y = 0
            #ctypes.windll.user32.MessageBoxW(0, str(controller.ViewOffset), "view offset", 1)
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "set document zoom level error", 1)
    
    # only for testing #
    def set_bitmaps(self):
        try:
            desktop = self.ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            oDoc = desktop.getCurrentComponent()
            #oPage = oDoc.DrawPages(0)
            #ctypes.windll.user32.MessageBoxW(0, str(oPage), "page", 1)
            
            defaultStyle = oDoc.getStyleFamilies().getByName("graphics").getByName("standard")#getElementNames()##
            #ctypes.windll.user32.MessageBoxW(0, str(defaultStyle.getPropertySetInfo().getProperties()), "styles", 1)

            controller = get_controller(self.frames)
            shape = get_first_shape_in_selection(controller)
            
            oProvider = self.ctx.getServiceManager().createInstance("com.sun.star.graphic.GraphicProvider")
            #uri = os.path.join(os.path.dirname(__file__), 'bitmap-pattern\\vertical_lines_red.png')
            uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/vertical_lines_red.png'
            
            propVal = PropertyValue()
            propVal.Name = "URL"
            propVal.Value = uri           
            getGraphFromUrl = oProvider.queryGraphic( (propVal,) )

            #oBitmapTable = oDoc.createInstance("com.sun.star.drawing.BitmapTable")
            #oBitmapTable.insertByName('red stripes', getGraphFromUrl)
            #ctypes.windll.user32.MessageBoxW(0, str(oBitmapTable), "bitmap table", 1)

            shape.FillStyle = BITMAP
            shape.FillBitmap = getGraphFromUrl

            #shape.Graphic = getGraphFromUrl
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "set bitmaps error", 1)   

            
### adds a spacing between border and fill pattern of the current selected shape ###
class BorderSpacing(unohelper.Base, XDispatch, XControlNotificationListener):            
    def __init__(self, ctx, frames):
        self.state = False
        self.listener = None
        self.ctx = ctx
        self.frames = frames
    
    def get_state(self):
        return self.state
        
    def set_state(state):
        self.state = state
    
    def dispatch(self, url, args):
        #self.state = not self.state
        ev = self.create_simple_event(url, self.state)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, state, enabled=True):
        try:
            controller = get_controller(self.frames)
            selection = controller.getSelection()
            if not selection:
                ctypes.windll.user32.MessageBoxW(0, no_selection, warning, 1)
                return
            
            if selection.getCount() > 1:
                ctypes.windll.user32.MessageBoxW(0, to_much_selection, warning, 1)
                return
            
            shape = get_first_shape_in_selection(controller)
            if is_border_spacing_group(shape):
                self.delete_border_spacing(shape)
            else:
                self.add_border_spacing(shape)

            return FeatureStateEvent(self, url, "", enabled, False, state)

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "border spacing event error", 1)
            
    def add_border_spacing(self, shape):
        try:
            if not shape:
                return
            
            #if shape.getShapeType() == "com.sun.star.drawing.GroupShape": 
            #    # refresh border spacing for selected group #
            #    bg_shape = get_filled_shape_of_group(shape)                    
            #    if not bg_shape:
            #        return
            #    bg_line_width = bg_shape.getPropertyValue("LineWidth")
            #    fg_shape = get_none_filled_shape_of_group(shape)
            #    if not fg_shape:
            #        return
            #    fg_line_width = fg_shape.getPropertyValue("LineWidth")
            #    
            #    if bg_line_width == fg_line_width:
            #        bg_shape.LineWidth = (bg_line_width + line_spacing)
            #    return
            
            controller = get_controller(self.frames)
            if not controller:
                return
            page = get_page(controller)
                
            # TODO: macht nicht für alle shapes Sinn... hier evtl. noch Prüfung einfügen
                
            # get properties of original shape #
            #type = shape.getShapeType() # e.g. "com::sun::star::drawing::LineShape"
            #ctypes.windll.user32.MessageBoxW(0, str(type), "shape type", 1)
            #size = shape.getSize()
            #position = shape.getPosition()
            #bitmap = shape.getPropertyValue("FillBitmapName")
            line_width = shape.getPropertyValue("LineWidth")
            line_style = shape.getPropertyValue("LineStyle")
            title = shape.getPropertyValue("Title")
            desc = shape.getPropertyValue("Description")
                       
            # create clone of shape #
            desktop = self.ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            oDoc = desktop.getCurrentComponent()
            frame = controller.getFrame()
            shape_clone = self.clone_shape(frame, shape)
            original_shape = shape
            
            # set new properties of background (original) shape and of new shape which is in front of the original shape #
            original_shape.LineColor = 16777215 #white
            original_shape.LineStyle = SolidLine
            original_shape.LineWidth = (line_width + line_spacing) # 2mm distance to each side
            # new shape is now selected after paste #
            selection = controller.getSelection()
            if not selection:
                return
            new_shape = selection.getByIndex(0)
            if not new_shape:
                return
            new_shape.FillStyle = NONE
            new_shape.LineStyle = line_style
            
            # group the two shapes to one group #
            xshapes = selection
            xshapes.add(original_shape)
            group = page.group(xshapes)
            
            # apply title and description of original shape for the whole group #
            group.setPropertyValue("Title", title)
            group.setPropertyValue("Description", desc)
            
            # select group #
            controller.select(group)
            
            # add to undo/redo history #
            add_to_undo_redo_history(self.ctx, "add_border_spacing", "Abstand zu Füllmuster", group, original_shape, controller)
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "add border spacing error", 1)
            
    def delete_border_spacing(self, shape):
        try:
            if not shape:
                return
            controller = get_controller(self.frames)
            page = get_page(controller)
            group = shape
            i = 0
            line_color = 0 #black
            
            # find cloned shape and delete it, change other shape to old line style and width #
            while i < group.getCount():
                s = group.getByIndex(i)
                if s.getPropertyValue("FillStyle") == NONE:
                    line_color = s.getPropertyValue("LineColor")
                    group.remove(s)
                else:
                    line_width = s.getPropertyValue("LineWidth")
                    s.LineWidth = (line_width - line_spacing)
                    s.LineColor = line_color
                    shape = s
                i = i+1
            page.ungroup(group)
            controller.select(shape)
                
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "delete border spacing error", 1)
    
    def clone_shape(self, frame, shape):
        try:
            oDispatchHelper = create_uno_service( "com.sun.star.frame.DispatchHelper" )
            oDispatchHelper.executeDispatch( frame, ".uno:Copy", "", 0, () )
            clone_shape = oDispatchHelper.executeDispatch( frame, ".uno:Paste", "", 0, () )
            return clone_shape
        
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "clone shape error", 1)


###############################################################################################################
###   Metadata dialog and functionality                                                                     ###
###############################################################################################################

metadata = dict([('title', ""), ('type', ""), ('language', ""), ('shortDesc', ""), ('longDesc', ""), ('keywords', ""), ('author', ""), ('status', ""), ('source', ""), ('rights', ""), ('method', ""), ('proofreader', ""), ('adaptions', ""), ('annotations', "")])


### opens the metadata dialog ###
class OpenMetaDataDialog(unohelper.Base, XDispatch, XControlNotificationListener):
    def __init__(self, ctx, frames):
        self.ctx = ctx
        self.frames = frames
        self.state = False
        self.listener = None
        self.dialog = None
        
        if not self.ctx:
            return
        self.smgr = self.ctx.ServiceManager
        if not self.smgr:
            return
        desktop = self.smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        if not desktop:
            return
        self.doc = desktop.getCurrentComponent()
    
    def get_state(self):
        return self.state
    
    def dispatch(self, url, args):
        #self.state = not self.state
        ev = self.create_simple_event(url, self.state)
        self.listener.statusChanged(ev)
    
    def addStatusListener(self, listener, url):
        self.listener = listener
        
    def removeStatusListener(self, listener, url): pass
    
    def controlEvent(self, ev): pass
    
    def create_simple_event(self, url, state, enabled=True):
        self.open_metadata_window()
        self.load_metadata()
        return FeatureStateEvent(self, url, "", enabled, False, state)

    def open_metadata_window(self):
        try:
            if not self.smgr:
                return
            if not self.doc:
                return
            
            metaDataDialog = "vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/MetaDataDialog.xdl"
            window = None
            
            toolkit = self.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
            controller = self.doc.getCurrentController()
            parent = self.doc.getParent()

            # Creates outer window (title name of this window is defined in WindowState configuration)
            desc = WindowDescriptor(TOP, "window", parent, -1, Rectangle(100, 100, 405, 265), SHOW | SIZEABLE | MOVEABLE | CLOSEABLE)
            if not toolkit:
                return
            window = toolkit.createWindow(desc)
            if not window:
                return
            window.setVisible(False)
            
            # Create inner window from dialog
            dp = self.smgr.createInstanceWithContext("com.sun.star.awt.ContainerWindowProvider", self.ctx)
            if not dp:
                return
            child = dp.createContainerWindow(metaDataDialog, "", window, None)
            if not child:
                return
            #ctypes.windll.user32.MessageBoxW(0, str(child), "child", 1)
            self.dialog = child
            child.setVisible(True)
            child.setPosSize(0, 0, 0, 0, POS)  # if the dialog is not placed at top left corner
            # TODO how to show the content of child directly in "window" instead in own window???
            # TODO how to give close button its functionality?
            
            btn_desc = child.getControl("CommandButton_Desc")
            if btn_desc:
                listener1 = ButtonListener(1, child, btn_desc, 0, 0)
                btn_desc.addActionListener(listener1)
                btn_desc.setEnable(False)
            
            model = child.getModel()
            if model:
                model.Step = 1
            
            btn_rights = child.getControl("CommandButton_Rights")
            if btn_rights:
                listener2 = ButtonListener(2, child, btn_rights, 0, 0)
                btn_rights.addActionListener(listener2)
            
            btn_annotations = child.getControl("CommandButton_Annotations")
            if btn_annotations:
                listener3 = ButtonListener(3, child, btn_annotations, 0, 0)
                btn_annotations.addActionListener(listener3)
            
            btn_save = child.getControl("CommandButton_Save")
            if btn_save:
                listener4 = ButtonListener(4, child, btn_save, 0, self.doc)
                btn_save.addActionListener(listener4)            
            
            btn_cancel = child.getControl("CommandButton_Cancel")
            if btn_cancel:
                listener5 = ButtonListener(5, child, btn_cancel, window, 0)
                btn_cancel.addActionListener(listener5)
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "open metadata dialog error", 1)
            
    ###  Loads all metadata from document into dialog  ###
    def load_metadata(self):
        try:
            if self.doc:
                props = self.doc.getDocumentProperties()
                if props:
                    metadata['title'] = props.Title
                    self.dialog.getControl("TextField_Title").setText(metadata['title'])

                    #metadata['language'] = props.Language # FIXME: not specified in global doc properties --> add own entry in user defined properties
                    #ctypes.windll.user32.MessageBoxW(0, str(metadata['language']), "language", 1)
                    
                    keywordList = props.Keywords
                    l = len(keywordList)
                    if l > 0:
                        metadata['keywords'] = keywordList[0]
                        k = 1
                        while k < l:
                            metadata['keywords'] = metadata['keywords'] + ", " + keywordList[k]
                            k = k + 1
                    self.dialog.getControl("TextField_Keywords").setText(metadata['keywords'])
                    
                    metadata['author'] = props.Author
                    self.dialog.getControl("TextField_Author").setText(metadata['author'])
                    
                    metadata['annotations'] = props.Description
                    self.dialog.getControl("TextField_Annotations").setText(metadata['annotations'])
                    
                    ### load or add user defined properties ###
                    userDefinedProps = props.getUserDefinedProperties()
                    if userDefinedProps:
                                            
                        try:
                            language = userDefinedProps.getPropertyValue("Language")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Language", OPTIONAL, self.dialog.getControl("ListBox_Language").getSelectedItem())
                            language = userDefinedProps.getPropertyValue("Language")
                        metadata['language'] = language
                        self.dialog.getControl("ListBox_Language").selectItem(metadata['language'], True)
                        
                        try:
                            type = userDefinedProps.getPropertyValue("Type")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Type", OPTIONAL, self.dialog.getControl("ListBox_Type").getSelectedItem())
                            type = userDefinedProps.getPropertyValue("Type")
                        metadata['type'] = type
                        self.dialog.getControl("ListBox_Type").selectItem(metadata['type'], True)

                        try:
                            shortDesc = userDefinedProps.getPropertyValue("ShortDesc")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("ShortDesc", OPTIONAL, self.dialog.getControl("TextField_ShortDesc").getText())
                            shortDesc = userDefinedProps.getPropertyValue("ShortDesc")
                        metadata['shortDesc'] = shortDesc
                        self.dialog.getControl("TextField_ShortDesc").setText(metadata['shortDesc'])
                        
                        try:
                            longDesc = userDefinedProps.getPropertyValue("LongDesc")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("LongDesc", OPTIONAL, self.dialog.getControl("TextField_LongDesc").getText())
                            longDesc = userDefinedProps.getPropertyValue("LongDesc")
                        metadata['longDesc'] = longDesc
                        self.dialog.getControl("TextField_LongDesc").setText(metadata['longDesc'])
                        
                        try:
                            status = userDefinedProps.getPropertyValue("Status")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Status", OPTIONAL, self.dialog.getControl("ListBox_Status").getSelectedItem())
                            status = userDefinedProps.getPropertyValue("Status")
                        metadata['status'] = status
                        self.dialog.getControl("ListBox_Status").selectItem(metadata['status'], True)
                        
                        try:
                            source = userDefinedProps.getPropertyValue("Source")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Source", OPTIONAL, self.dialog.getControl("TextField_Source").getText())
                            source = userDefinedProps.getPropertyValue("Source")
                        metadata['source'] = source
                        self.dialog.getControl("TextField_Source").setText(metadata['source'])
                        
                        try:
                            rights = userDefinedProps.getPropertyValue("Rights")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Rights", OPTIONAL, self.dialog.getControl("TextField_Rights").getText())
                            rights = userDefinedProps.getPropertyValue("Rights")
                        metadata['rights'] = rights
                        self.dialog.getControl("TextField_Rights").setText(metadata['rights'])
                        
                        try:
                            method = userDefinedProps.getPropertyValue("Method")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Method", OPTIONAL, self.dialog.getControl("ListBox_Method").getSelectedItem())
                            method = userDefinedProps.getPropertyValue("Method")
                        metadata['method'] = method
                        self.dialog.getControl("ListBox_Method").selectItem(metadata['method'], True)
                        
                        try:
                            proofreader = userDefinedProps.getPropertyValue("Proofreader")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Proofreader", OPTIONAL, self.dialog.getControl("TextField_Proofreader").getText())
                            proofreader = userDefinedProps.getPropertyValue("Proofreader")
                        metadata['proofreader'] = proofreader
                        self.dialog.getControl("TextField_Proofreader").setText(metadata['proofreader'])
                        
                        try:
                            adaptions = userDefinedProps.getPropertyValue("Adaptions")
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Adaptions", OPTIONAL, self.dialog.getControl("TextField_Adaptions").getText())
                            adaptions = userDefinedProps.getPropertyValue("Adaptions")
                        metadata['adaptions'] = adaptions
                        self.dialog.getControl("TextField_Adaptions").setText(metadata['adaptions'])

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "load metadata error", 1)


### listener for buttons in metadata dialog ###
class ButtonListener(unohelper.Base, XActionListener):

    ### parameters: kind = button id, dialog = metadata dialog, button = current button element, window = parent window, document = drawing document ###
    def __init__(self, kind, dialog, button, window, document):
        self.kind = kind
        self.dialog = dialog
        self.btn = button
        self.window = window # only needed for close button
        self.doc = document # only needed for save button

    def disposing(self, ev):
        pass

    # XActionListener
    def actionPerformed(self, ev):
        try:
            model = self.dialog.getModel()
            if self.kind == 1:
                model.Step = 1
                self.enableButtons()
                self.btn.setEnable(False)
            elif self.kind == 2:
                model.Step = 2
                self.enableButtons()
                self.btn.setEnable(False)
            elif self.kind == 3:
                model.Step = 3
                self.enableButtons()
                self.btn.setEnable(False)
            elif self.kind == 4:
                self.saveMetaData()
                self.dialog.dispose()
                #self.window.dispose() # FIXME: error = 'int' object has no attribute 'dispose'
            elif self.kind == 5:
                self.dialog.dispose()
                self.window.dispose()
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "button listener error", 1)

    ### enables the three register buttons ###
    def enableButtons(self):
        if self.dialog:
            self.dialog.getControl("CommandButton_Desc").setEnable(True)
            self.dialog.getControl("CommandButton_Rights").setEnable(True)
            self.dialog.getControl("CommandButton_Annotations").setEnable(True)

    ### saves the metadata ###
    def saveMetaData(self):
        try:
            if self.dialog:
                #self.dialog.getControl("TextField_Title").setText("Titel der Grafik")
                
                props = self.doc.getDocumentProperties()
                if props:
                    metadata['title'] = self.dialog.getControl("TextField_Title").getText()
                    props.Title = metadata['title']
                    
                    #metadata['language'] = props.Language ### FIXME: not specified in global doc properties --> add own entry in user defined properties
                    #ctypes.windll.user32.MessageBoxW(0, str(metadata['language']), "language", 1)
                    
                    keywords = self.dialog.getControl("TextField_Keywords").getText()
                    keywordList = keywords.split(",")
                    keywordList = [s.strip() for s in keywordList]
                    props.Keywords = tuple(keywordList)
                    
                    metadata['author'] = self.dialog.getControl("TextField_Author").getText()
                    props.Author = metadata['author']
                    
                    metadata['annotations'] = self.dialog.getControl("TextField_Annotations").getText()
                    props.Description = metadata['annotations']
                    
                    ### save user defined properties ###
                    userDefinedProps = props.getUserDefinedProperties()
                    if userDefinedProps:
                        metadata['language'] = self.dialog.getControl("ListBox_Language").getSelectedItem()
                        try:
                            userDefinedProps.setPropertyValue("Language", metadata['language'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Language", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Language", metadata['language'])
                    
                        metadata['type'] = self.dialog.getControl("ListBox_Type").getSelectedItem()
                        try:
                            userDefinedProps.setPropertyValue("Type", metadata['type'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Type", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Type", metadata['type'])

                        metadata['shortDesc'] = self.dialog.getControl("TextField_ShortDesc").getText()
                        try:
                            userDefinedProps.setPropertyValue("ShortDesc", metadata['shortDesc'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("ShortDesc", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("ShortDesc", metadata['shortDesc'])
                            
                        metadata['longDesc'] = self.dialog.getControl("TextField_LongDesc").getText()
                        try:
                            userDefinedProps.setPropertyValue("LongDesc", metadata['longDesc'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("LongDesc", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("LongDesc", metadata['longDesc'])
                        
                        metadata['status'] = self.dialog.getControl("ListBox_Status").getSelectedItem()
                        try:
                            userDefinedProps.setPropertyValue("Status", metadata['status'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Status", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Status", metadata['status'])
                        
                        metadata['source'] = self.dialog.getControl("TextField_Source").getText()
                        try:
                            userDefinedProps.setPropertyValue("Source", metadata['source'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Source", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Source", metadata['source'])
                        
                        metadata['rights'] = self.dialog.getControl("TextField_Rights").getText()
                        try:
                            userDefinedProps.setPropertyValue("Rights", metadata['rights'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Rights", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Rights", metadata['rights'])
                        
                        metadata['method'] = self.dialog.getControl("ListBox_Method").getSelectedItem()
                        try:
                            userDefinedProps.setPropertyValue("Method", metadata['method'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Method", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Method", metadata['method'])
                        
                        metadata['proofreader'] = self.dialog.getControl("TextField_Proofreader").getText()
                        try:
                            userDefinedProps.setPropertyValue("Proofreader", metadata['proofreader'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Proofreader", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Proofreader", metadata['proofreader'])
                        
                        metadata['adaptions'] = self.dialog.getControl("TextField_Adaptions").getText()
                        try:
                            userDefinedProps.setPropertyValue("Adaptions", metadata['adaptions'])
                        except UnknownPropertyException:
                            userDefinedProps.addProperty("Adaptions", OPTIONAL, "")
                            userDefinedProps.setPropertyValue("Adaptions", metadata['adaptions'])
                        
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "save metadata error", 1)



###############################################################################################################
###   Creation of toolbar and all frames (elements)                                                         ###
###############################################################################################################

### class representing the toolbar elements and providing their functionalities ###        
class Frame(object):

### constants ###    
    # unit constants #
    MM = 0
    CM = 1
    IN = 2
    PT = 3
    PX = 4
    PERCENT = 5
    
    DPI = 96
    
    # property constants #
    X = 1
    Y = 2
    WIDTH = 4
    HEIGHT = 8
##  TITLE = 16
##  DESC = 32

    # pattern constants --> order has to be the same order as patterns were added in createItemWindow function #
    NO_PATTERN = 0
    CIRCLES = 1
    DASHED = 2
    DIAGONAL_1 = 3
    DIAGONAL_2 = 4
    DOTTED = 5
    FULL_PATTERN = 6
    GRID = 7
    H_LINE = 8
    STAIR = 9
    V_LINE = 10
    
    # line constants #
    SOLID_LINE = 0
    DASHED_LINE = 1
    DOTTED_LINE = 2
    
    
    def __init__(self, frame, ctx):
        self.frame = frame
        self.ctx = ctx
        self.current_unit = self.MM
        self.current_pattern = self.NO_PATTERN
        self.current_linestyle = self.SOLID_LINE
        self.set_listener()
        self.lastSelected = None # shape that was selected before new selection
        self.firstSelected = False # true if shape was selected quite recently, false if shape is selected at least one operation before
        # have to keep original position and size for % ?
    
    def set_item(self, item, value):
        cmd = item.command[len(IMPL_NAME)+1:]
                
        if cmd in ("X", "Y", "Width", "Height", "Unit", "KeepRatio", "Title", "Desc", "TitleDescButton", "Patterns", "Lines"):
            self.__dict__[cmd.lower()] = value
        
        if cmd == "Unit":
            self.unit.addItemListener(UnitListListener(self))
        elif cmd == "Patterns":
            self.patterns.addItemListener(PatternListListener(self))
        elif cmd == "Lines":
            self.lines.addItemListener(LineListListener(self))

        elif (cmd == "KeepRatio") or (cmd == "TitleDescButton") or (cmd == "CheckToolButton") or (cmd == "MetaDataButton") or (cmd == "TangramAppButton") or (cmd == "BorderSpacingButton"):
            pass
##      elif (cmd == "Title") or (cmd == "Desc"):
##          listener = EditListener(self, Frame.__dict__[cmd.upper()])
##          box = self.__dict__[cmd.lower()]
##          box.addKeyListener(listener)
##          box.addFocusListener(listener)
##          box.addTextListener(listener)
        else:
            listener = NumericFieldListener(self, Frame.__dict__[cmd.upper()])
            box = self.__dict__[cmd.lower()]
            box.addKeyListener(listener)
            box.addFocusListener(listener)
            box.addSpinListener(listener)
            box.addTextListener(listener)

        self.enable_fields(False)       
        
    
    def set_listener(self):
        controller = self.get_controller()
        if not controller:
            return
        controller.addSelectionChangeListener(SelectionChangeListener(self))
        self.propertiesListener = PropertyChangeListener(self)

    def get_controller(self):
        try:
            return self.frame.getController()
        except Exception as e:
            print(e)
    
    def enable_fields(self, enabled):
        try:
            if self.x:
                self.x.setEnable(enabled)
            if self.y:
                self.y.setEnable(enabled)
            if self.height:
                self.height.setEnable(enabled)
            if self.width:
                self.width.setEnable(enabled)
            if self.patterns:
                self.patterns.setEnable(enabled)
            if self.lines:
                self.lines.setEnable(enabled)
##          if self.title:
##              self.title.setEnable(enabled)
##          if self.desc:
##              self.desc.setEnable(enabled)
        except Exception as e:
            print(e)
    
    def get_unit(self):
        u = self.MM
        if  self.unit:
            unit = self.unit.getSelectedItem()
            if unit == "mm":
                pass
            elif unit == "cm":
                u = self.CM
            elif unit == "in":
                u = self.IN
            elif unit == "pt":
                u = self.PT
            elif unit == "px":
                u = self.PX
            elif unit == "%":
                u = self.PERCENT
        return u    
    
    def to_unit(self, value, unit):
        if unit == self.MM:
            return value / 100.0
        elif unit == self.CM:
            return value / 1000.0
        elif unit == self.IN:
            return value / 100.0 / 25.4
        elif unit == self.PT:
            return value / 100.0 / 25.4 * 72
        elif unit == self.PX:
            return value / 100.0 / 25.4 * self.DPI
        else:
            return value
    
    def from_unit(self, value, unit):
        if unit == self.MM:
            return value * 100.0
        elif unit == self.CM:
            return value * 1000.0
        elif unit == self.IN:
            return value * 100.0 * 25.4
        elif unit == self.PT:
            return value * 100.0 * 25.4 / 72
        elif unit == self.PX:
            return value * 100.0 * 25.4 / self.DPI
        else:
            return value 
          
    ### fill toolbar elements with data of current selected shape ###
    def fill_values(self, selection, size_only=False):
        try:
            unit = self.current_unit
            controller = self.get_controller()
            if not selection:
                selection = controller.getSelection()
            if not selection:
                return
            
            page = None
            if controller:
                page = get_page(controller)
            shape = selection
            if shape.getImplementationName() == "com.sun.star.drawing.SvxShapeCollection":
                shape = selection.getByIndex(0)
            if not shape:
                return

            # if shape is group (border spacing is activated) handle both shapes #
            if shape.getShapeType() == "com.sun.star.drawing.GroupShape": 
                group = shape
                none_filled_shape = get_none_filled_shape_of_group(group)
                if not none_filled_shape:
                    return
                shape = get_filled_shape_of_group(group)              
                if not shape:
                    return

                # beim Ändern der Linienstärke muss die Linienstärke des nicht gefüllten Shapes angepasst werden                     
                lineWidth = none_filled_shape.getPropertyValue("LineWidth")
                #ctypes.windll.user32.MessageBoxW(0, str(lineWidth), "line width", 1)
                shape.LineWidth = lineWidth + line_spacing
                    
                # TODO: schön wäre es, wenn der borderspacing button aktiviert dargestellt wäre und als Titel "... entfernen" da stehen würde
                #ctypes.windll.user32.MessageBoxW(0, str(self.borderspacingbutton), "border spacing button", 1)
                #self.borderspacingbutton.set_state(True)
            #else:
                #self.borderspacingbutton.set_state(False)
            
            # update bitmap list entry #
            bitmap = shape.getPropertyValue("FillBitmapName")
            pattern = 0
            if bitmap:
                pattern = self.get_pattern_list_item(bitmap)
                #ctypes.windll.user32.MessageBoxW(0, str(bitmap), "bitmap", 1)
            #ctypes.windll.user32.MessageBoxW(0, "fill_values \n\n pattern--> "+str(pattern) +"\n\n bitmap --> "+str(bitmap), "debug-window fill_values 1/1" , 1)
            self.patterns.selectItemPos(pattern, True)
            
            # update line style list entry #
            linestyle = shape.getPropertyValue("LineStyle")
            if linestyle == SolidLine:
                self.lines.selectItemPos(self.SOLID_LINE, True)
            elif linestyle == DashedLine:
                lineDash = shape.getPropertyValue("LineDash")
                if lineDash.Dashes == 1: # TODO find other criteria, but at this time LineDashName does not work
                    self.lines.selectItemPos(self.DASHED_LINE, True)
                else:
                    self.lines.selectItemPos(self.DOTTED_LINE, True)
                    # beim Ändern der Linienstärke muss die Länge der Dots angepasst werden 
                    lineWidth = shape.getPropertyValue("LineWidth")
                    lineDash.DotLen = lineWidth
                    shape.LineDash = lineDash

    ##          title = shape.getPropertyValue("Title")
    ##          desc = shape.getPropertyValue("Description")
            
            # update position and size text field #
            position = shape.getPosition()
            size = shape.getSize()
            if unit == self.PERCENT: #weglassen?
                width = 100
                height = 100
            else:       
                _x = position.X - page.BorderLeft
                _y = position.Y - page.BorderTop
                _width = size.Width
                _height = size.Height
                
                x = self.to_unit(_x, unit)
                y = self.to_unit(_y, unit)
                width = self.to_unit(_width, unit)
                height = self.to_unit(_height, unit)
            
            if not size_only:
                self.x.setProperty("Value", x)
                self.y.setProperty("Value", y)
    ##          self.title.setText(title)
    ##          self.desc.setText(desc)
            self.width.setProperty("Value", width)
            self.height.setProperty("Value", height)
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "fill values error", 1)

    
    ### is called if another shape is selected ###
    def selection_changed(self, ev):
        controller = self.get_controller()
        if not controller:
            return
        selection = controller.getSelection()
        if selection:
            self.enable_fields(True)
            try:
                selectedShape = selection.getByIndex(0)
                self.lastSelected = selectedShape
                selectedShape.addPropertyChangeListener("Position", self.propertiesListener)
                selectedShape.addPropertyChangeListener("Size", self.propertiesListener)
                if selectedShape == self.lastSelected:
                    self.firstSelected = False
                else:
                    self.firstSelected = True
            except Exception as e:
                print(e)
                #ctypes.windll.user32.MessageBoxW(0, str(e), "selection error", 1)   
            self.fill_values(selection)
        else:
            self.enable_fields(False)
            try:
                if self.lastSelected:
                    self.lastSelected.removePropertyChangeListener("Position", self.propertiesListener)
                    self.lastSelected.removePropertyChangeListener("Size", self.propertiesListener)
            except Exception as e:
                print(e)
                #ctypes.windll.user32.MessageBoxW(0, str(e), "listener remove error", 1) 
    
    ### is called if a property of the selected shape was changed from outside (e.g. by mouse) ###
    def property_change(self, ev):
        try:
            #ctypes.windll.user32.MessageBoxW(0, str(ev), "property change event", 1)
            controller = self.get_controller()
            if not controller:
                return
            selection = get_first_shape_in_selection(controller)
            if not selection:
                return
            #changed_property = ev.PropertyName
            #ctypes.windll.user32.MessageBoxW(0, str(changed_property), "property change name", 1)
            #if changed_property == "Size":
                #ctypes.windll.user32.MessageBoxW(0, str(old_size), "old value", 1)
                #ctypes.windll.user32.MessageBoxW(0, str(ev.NewValue), "new value", 1)
                #if ev.OldValue == ev.NewValue:                
                #    ctypes.windll.user32.MessageBoxW(0, str(changed_property), "property change event", 1)
            self.fill_values(selection)            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "property change error", 1)
    
    ### save values from toolbar elements into shape object ###
    def apply(self, kind):
        try:
            unit = self.current_unit
            controller = self.get_controller()
            if not controller:
                return
            selection = controller.getSelection()
            shape = selection.getByIndex(0)        
        
            if (kind & self.X) or (kind & self.Y):
                self.apply_position(kind, unit, controller, shape)
            if (kind & self.WIDTH) or (kind & self.HEIGHT):
                self.apply_size(kind, unit, shape)
##          if (kind & self.TITLE) or (kind & self.DESC):
##              self.apply_title_desc(kind, shape)

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "apply error", 1)
    
    ### save position which was set in the numeric fields into the shape object ###
    def apply_position(self, kind, unit, controller, shape):
        try:
            page = get_page(controller)
            position = shape.getPosition()
            
            if kind & self.X:
                _x = self.x.getValue()
                if unit == self.PERCENT:
                    x = (position.X - page.BorderLeft) * _x / 100.0 + page.BorderLeft
                else:
                    x = self.from_unit(_x, unit) + page.BorderLeft
                if position.X != int(x):
                    position.X = x
                    shape.setPosition(position)
            
            if kind & self.Y:
                _y = self.y.getValue()
                if unit == self.PERCENT:
                    y = (position.Y - page.BorderTop) * _y / 100.0 + page.BorderTop
                else:
                    y = self.from_unit(_y, unit) + page.BorderTop
                if position.Y != int(y):
                    position.Y = y
                    shape.setPosition(position)
        except Exception as e:
            print(e)
    
    ### save size which was set in the numeric fields into the shape object ###
    def apply_size(self, kind, unit, shape):
        try:
            if self.keepratio.get_state():
                size = shape.getSize()
                
                ratio = 0
                if kind & self.WIDTH:
                    _width = self.width.getValue()
                    if unit == self.PERCENT:
                        ratio = _width / 100.0
                        width = size.Width * _width / 100.0
                    else:
                        width = self.from_unit(_width, unit)
                        ratio = width / size.Width
                    height = size.Height * ratio
                
                elif kind & self.HEIGHT:
                    _height = self.height.getValue()
                    if unit == self.PERCENT:
                        ratio = _height / 100.0
                        height = size.Height * _height / 100.0
                    else:
                        height = self.from_unit(_height, unit)
                        ratio = height / size.Height
                    width = size.Width * ratio
                
                size.Width = width
                size.Height = height
                shape.setSize(size)
                self.fill_values(None, size_only=True)
            else:
                # minimum width and height are 1
                if kind & self.WIDTH:
                    size = shape.getSize()
                    
                    _width = self.width.getValue()
                    if unit == self.PERCENT:
                        width = size.Width * _width / 100.0
                    else:
                        width = self.from_unit(_width, unit)
                    if size.Width != int(width):
                        size.Width = width if width > 0 else 1
                        shape.setSize(size)
                
                if kind & self.HEIGHT:
                    size = shape.getSize()
                    
                    _height = self.height.getValue()
                    if unit == self.PERCENT:
                        height = size.Height * _height / 100.0
                    else:
                        height = self.from_unit(_height, unit)
                    if size.Height != int(height):
                        size.Height = height if height > 0 else 1
                        shape.setSize(size)
        except Exception as e:
            print(e)
    
    ### save title and description which was set in the text fields into the shape object ###
##  def apply_title_desc(self, kind, shape):
##      if kind & self.TITLE:
##          title = shape.getPropertyValue("Title")         
##          _title = self.title.getText()
##          if title != _title:
##              title = _title
##              shape.setPropertyValue("Title", title)
##              
##      if kind & self.DESC:
##          desc = shape.getPropertyValue("Description")        
##          _desc = self.desc.getText()
##          if desc != _desc:
##              desc = _desc
##              shape.setPropertyValue("Description", desc)


    ### assign all shapes in selection the given pattern as filling bitmap ###
    def apply_pattern(self, pattern):
        try:
            if self.firstSelected: # do nothing if apply_pattern function was only called because a shape was selected 
                self.firstSelected = False
                return
        
            controller = self.get_controller()
            if not controller:
                return
            selection = controller.getSelection()
            if not selection:
                return

            count = selection.getCount()
            if count > 0:
                i = 0
                while i < count:
                    shape = selection.getByIndex(i)
                    self.apply_pattern_for_shape(pattern, shape)
                    i = i + 1

        except Exception as e:
            str_Ex = type(exception).__name__
            #ctypes.windll.user32.MessageBoxW(0, "test " +str(str_Ex), "apply pattern error", 1)

    ### assign shape the given pattern as filling bitmap ###
    def apply_pattern_for_shape(self, pattern, shape):
        try:
            if not shape:
                return
            
            # handle border-filling-spacing group
            if shape.getShapeType() == "com.sun.star.drawing.GroupShape": 
                # find background shape which includes the filling and apply the pattern for this shape #
                is_spacing_group = False
                group = shape
                count = group.getCount()
                if count == 2:
                    s1 = group.getByIndex(0)
                    s2 = group.getByIndex(1)
                    if s1.getSize() == s2.getSize() and s1.getPosition().X == s2.getPosition().X and s1.getPosition().Y == s2.getPosition().Y:
                        shape = get_filled_shape_of_group(shape)
                        is_spacing_group = True
                        if not shape:
                            return
                            
                if not is_spacing_group:
                    i = 0
                    while i < count:
                        shape = group.getByIndex(i)
                        self.apply_pattern_for_shape(pattern, shape)
                        i = i + 1
                    return

            self.apply_and_save_pattern(pattern, shape)
                
        except Exception as e:
            str_Ex = type(exception).__name__
            #ctypes.windll.user32.MessageBoxW(0, "test " +str(str_Ex), "apply pattern error", 1)

    def apply_and_save_pattern(self, pattern, shape):
        try:
            if not shape:
                return
        
            undo_props = self.get_undo_filling_props(shape)
            pattern_graphic = self.get_pattern_graphic(pattern)
            
            #testing
            #patter_string = str(pattern_graphic)
            #ctypes.windll.user32.MessageBoxW(0, "old_fill_value --> "+str(old_fill_value), "debug-window apply_pattern 1/4" , 1)
            #ctypes.windll.user32.MessageBoxW(0, "old_fill_value --> "+str(old_fill_style), "debug-window apply_pattern 2/4" , 1)
            #ctypes.windll.user32.MessageBoxW(0, "pattern_graphic --> " +patter_string +"\n|patter  --> "+str(pattern)+"\n| undo_props --> "+str(undo_props), "debug-window apply_pattern 3/4" , 1)
            #ctypes.windll.user32.MessageBoxW(0, "shape  --> " +str(shape.FillBitmapName), "debug-window apply_pattern 4/4" , 1)
            #ctypes.windll.user32.MessageBoxW(0, "pattern" + str(pattern), "debug-window" , 1)
            #ctypes.windll.user32.MessageBoxW(0, "undo_props" +str(undo_props), "debug-window" , 1)
            
            if pattern_graphic or shape.FillBitmapName:
                shape.FillStyle = BITMAP
                shape.FillBitmap = pattern_graphic
                #shape.FillBitmapName = "test" 
            else: # no pattern is selected
                shape.FillStyle = SOLID
                shape.FillColor = 16777215 # white
                #shape.FillBitmapName = "None_test"
            
            # save new filling #
            redo_props = [shape, pattern_graphic]
            #add_to_undo_redo_history(self.ctx, "apply_pattern", "Füllmuster anwenden", undo_props, redo_props, controller)
        
        except Exception as e:
            str_Ex = type(exception).__name__
            #ctypes.windll.user32.MessageBoxW(0, "test " +str(str_Ex), "apply pattern error", 1)
            
    
    ### get undo properties for shape filling ###
    def get_undo_filling_props(self, shape):
        try:
            old_fill_style = shape.getPropertyValue("FillStyle")
            old_fill_value = None
            if old_fill_style == BITMAP:
                old_fill_value = shape.getPropertyValue("FillBitmap")
            elif old_fill_style == SOLID:
                old_fill_value = shape.getPropertyValue("FillColor")
            # TODO: handle other fill styles
            return [shape, old_fill_style, old_fill_value]
        
        except Exception as e:
            print(e)
    
    ### get xgraphic for the given pattern id ###
    def get_pattern_graphic(self, pattern):
        try:
            oProvider = self.ctx.getServiceManager().createInstance("com.sun.star.graphic.GraphicProvider")
            uri = ''

            if pattern == self.NO_PATTERN:
                return None
            elif pattern == self.FULL_PATTERN:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/full_pattern.png'
            elif pattern == self.H_LINE:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/horizontal_lines.png'
            elif pattern == self.V_LINE:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/vertical_lines.png'
            elif pattern == self.CIRCLES:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/circles.png'
            elif pattern == self.DASHED:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/dashed_lines.png'
            elif pattern == self.DOTTED:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/dotted_pattern.png'
            elif pattern == self.GRID:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/grid_pattern.png'
            elif pattern == self.STAIR:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/stair_pattern.png'
            elif pattern == self.DIAGONAL_1:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/diagonal_line1.png'
            elif pattern == self.DIAGONAL_2:
                uri = 'vnd.sun.star.extension://tud.mci.tangram.PropertiesToolbar/bitmap-pattern/diagonal_line2.png'
                
            propVal = PropertyValue()
            propVal.Name = "URL"
            propVal.Value = uri           
            return oProvider.queryGraphic( (propVal,) )
        
        except Exception as e:
            print(e)

    ### get list item id for the given filling bitmap url ###
    def get_pattern_list_item(self, pattern_name):
        try:
            # pattern_name is name of the bitmap without ending (type)
            p = self.NO_PATTERN
            if pattern_name == "full_pattern":
                p = self.FULL_PATTERN
            elif pattern_name == "horizontal_lines":
                p = self.H_LINE
            elif pattern_name == "vertical_lines":    
                p = self.V_LINE
            elif pattern_name == "circles":
                p = self.CIRCLES
            elif pattern_name == "dashed_lines":
                p = self.DASHED
            elif pattern_name == "dotted_pattern":
                p = self.DOTTED
            elif pattern_name == "grid_pattern":
                p = self.GRID
            elif pattern_name == "stair_pattern":
                p = self.STAIR
            elif pattern_name == "diagonal_line1":
                p = self.DIAGONAL_1
            elif pattern_name == "diagonal_line2":
                p = self.DIAGONAL_2
            return p
        except Exception as e:
            print(e)
            
    ### assign all shapes in selection the given line style ###        
    def apply_linestyle(self, linestyle):
        try:
            if self.firstSelected: # do nothing if apply_pattern function was only called because a shape was selected 
                self.firstSelected = False
                return
            
            controller = self.get_controller()
            if not controller:
                return
            selection = controller.getSelection()
            if not selection:
                return

            count = selection.getCount()
            if count > 0:
                i = 0
                while i < count:
                    shape = selection.getByIndex(i)
                    self.apply_linestyle_for_shape(linestyle, shape)
                    i = i + 1

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "apply line style error", 1)
            
            
    ### assign shape the given line style ###
    def apply_linestyle_for_shape(self, linestyle, shape):
        try:
            if not shape:
                return
            
            # handle border-filling-spacing group
            if shape.getShapeType() == "com.sun.star.drawing.GroupShape": 
                # find background shape which includes the filling and apply the pattern for this shape #
                is_spacing_group = False
                group = shape
                count = group.getCount()
                if count == 2:
                    s1 = group.getByIndex(0)
                    s2 = group.getByIndex(1)
                    if s1.getSize() == s2.getSize() and s1.getPosition().X == s2.getPosition().X and s1.getPosition().Y == s2.getPosition().Y:
                        shape = get_none_filled_shape_of_group(shape)
                        is_spacing_group = True
                        if not shape:
                            return
                            
                if not is_spacing_group:
                    i = 0
                    while i < count:
                        shape = group.getByIndex(i)
                        self.apply_linestyle_for_shape(linestyle, shape)
                        i = i + 1
                    return
            self.apply_and_save_linestyle(linestyle, shape)

        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "apply line style error", 1)
    
    def apply_and_save_linestyle(self, linestyle, shape):
        try:
            if not shape:
                return

            undo_props = self.get_undo_line_props(shape)

            if linestyle == self.SOLID_LINE:
                shape.LineStyle = SolidLine
            else:    
                shape.LineStyle = DashedLine
                #ctypes.windll.user32.MessageBoxW(0, str(linestyle), "line style to apply", 1)
                lineDash = LineDash()
                #ctypes.windll.user32.MessageBoxW(0, str(lineDash), "lineDash struct", 1)
                if linestyle == self.DASHED_LINE:                    
                    #shape.LineDashName = "Tangram dashed line" # warum geht das nicht?
                    lineDash.Dashes = 1
                    lineDash.DashLen = 1000
                    lineDash.Distance = 500
                    
                elif linestyle == self.DOTTED_LINE:
                    #shape.LineDashName = "dotted line"
                    lineWidth = shape.getPropertyValue("LineWidth")
                    lineDash.Dots = 1
                    lineDash.DotLen = lineWidth
                    lineDash.Distance = 500
                shape.LineDash = lineDash
                #ctypes.windll.user32.MessageBoxW(0, str(shape.LineDashName), "lineDash name", 1)
                
            # save new line style #
            redo_props = [shape, linestyle]
            #add_to_undo_redo_history(self.ctx, "apply_linestyle", "Linienstil anwenden", undo_props, redo_props, controller)
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "apply and save linestyle error", 1)
    
    def get_undo_line_props(self, shape):
        try:
            old_line_style = shape.getPropertyValue("LineStyle")
            old_line_value = None
            if old_line_style == SolidLine:
                old_line_value = shape.getPropertyValue("LineColor")
            elif old_line_style == DashedLine:
                old_line_value = shape.getPropertyValue("LineDash")
            # TODO: handle other line styles
            
            return [shape, old_line_style, old_line_value]
            
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "get undo linestyle props error", 1)


###  container for all toolbar elements  ###
class FramesContainer(object):
    def __init__(self):
        self.items = []
        self.ctx = None
    
    def find(self, value):
        i = 0
        for item in self.items:
            if item.frame == value.frame:
                return i
            i += 1
        raise KeyError()
    
    def add(self, value):
        try:
            self.find(value)
        except:
            self.items.append(value)
    
    def remove(self, value):
        try:
            n = self.find(value)
            self.items.pop(n)
        except:
            pass
    
    def get(self, value):
        try:
            n = self.find(value)
            return self.items[n]
        except:
            return None
    
    def add_item(self, item, value, ctx):
        try:
            frame = self.get(item)
            self.ctx = ctx
            if not frame:
                frame = Frame(item.frame, ctx)
                self.add(frame)
            frame.set_item(item, value)
        except Exception as e:
            print(e)


frames = FramesContainer()


###  abstract class for creation of toolbar elements  ###
class ToolbarControllerBase(unohelper.Base, XInitialization, XServiceInfo, XStatusListener, XSubToolbarController, XToolbarController):
    
    def __init__(self, ctx, *args):
        self.ctx = ctx
        self.initialize(args)
    
    # XInitialization
    def initialize(self, args):
        try:
            for arg in args:
                name = arg.Name
                #ctypes.windll.user32.MessageBoxW(0, str(name), "arg.Name", 1)
                if name == 'Frame':
                    self.frame = arg.Value
                elif name == 'CommandURL':
                    self.command = arg.Value
        except Exception as e:
            print(e)
    
    # XServiceInfo
    def supportsService(self, name):
        return (name == "com.sun.star.frame.ToolbarController")
    def getImplementationName(self):
        return self.IMPLE_NAME
    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ToolbarController",)
    
    # XStatusListener
    def statusChanged(self, state): pass
            
    # XSubToolbarController
    def opensSubToolbar(self):
        return False
    def getSubToolbarName(self): return ""
    def functionSelected(self, command): pass
    def updateImage(self): pass
    
    # XToolbarController
    def execute(self, mod): pass
    def click(self): pass
    def doubleClick(self): pass
    def createPopupWindow(self):
        return None
    
    def createItemWindow(self, parent):
        self.parent = parent


###  creates concrete toolbar elements  ###
class ToolbarController(ToolbarControllerBase):
    
    def __init__(self, ctx, *args):
        ToolbarControllerBase.__init__(self, ctx, *args)
        self.ctx = ctx
    
    def getImplementationName(self):
        return IMPLE_NAME
    
    def createItemWindow(self, parent):
        try:
            cmd = self.command
            
            if cmd.endswith("Label"):
                label = str(cmd)
                label = label[len(IMPL_NAME)+1:]
                label = label[:-5]
                label += ":  "
                width = int(2+len(label)*6)
                box = create_window(parent.getToolkit(), parent, SIMPLE, "fixedtext", SHOW + RIGHT, 5, 10, width, 15)
    #            try:
    #                t = box.getPropertySetInfo().getProperties()
    #            except Exception as e:
    #                print(e)
    #                ctypes.windll.user32.MessageBoxW(0, str(t), "box", 1)
                box.setText(str(label))
                
    ##      elif cmd.endswith("Title"):
    ##          box = create_window(parent.getToolkit(), parent, SIMPLE, "edit", SHOW, 5, 10, 150, 15)
    ##              
    ##      elif cmd.endswith("Desc"):
    ##          box = create_window(parent.getToolkit(), parent, SIMPLE, "edit", SHOW, 5, 10, 400, 15)
            
            elif cmd.endswith("Unit"):
                box = create_window(parent.getToolkit(), parent, SIMPLE, "listbox", SHOW + DROPDOWN, 5, 2, 55, 23)
                box.addItems(("mm", "cm", "in", "pt", "px", "%"), 0)
                box.selectItemPos(0, True)
                box.setDropDownLineCount(6)

            elif cmd.endswith("Patterns"):
                box = create_window(parent.getToolkit(), parent, SIMPLE, "listbox", SHOW + DROPDOWN, 5, 2, 110, 23)
                box.addItems(("no pattern", "circles", "dashed lines", "diagonal line 1", "diagonal line 2", "dotted", "full pattern", "grid", "horizontal line", "stairs", "vertical line"), 0)
                # TODO: generic adding of items based on pattern images existent in the folder (no pattern has no image and therefore has to be always there as first entry)
                #try:
                #    box.getModel().setItemText(0, "hm")
                #except Exception as e:
                #    print(e)
                box.selectItemPos(0, True)
                box.setDropDownLineCount(11)
                #controller = frames.items[0].frame.getController()
                #ctypes.windll.user32.MessageBoxW(0, str(parent), "frames", 1)
                
            elif cmd.endswith("Lines"):
                box = create_window(parent.getToolkit(), parent, SIMPLE, "listbox", SHOW + DROPDOWN, 5, 2, 110, 23)
                box.addItems(("solid", "dashed line", "dotted line"), 0)
                box.selectItemPos(0, True)
                box.setDropDownLineCount(3)
            
            else:
                #x = 5 if cmd.endswith("X") or cmd.endswith("Width") else 10
                box = create_window(parent.getToolkit(), parent, SIMPLE, "numericfield", SHOW + SPIN, 5, 2, 65, 23)
                box.setDecimalDigits(4)
                box.enableRepeat(True)
                
                if cmd.endswith("Width") or cmd.endswith("Height"):
                    box.setMin(0.0)
                    
            frames.add_item(self, box, self.ctx)
            return box
        except Exception as e:
            print(e)
           

###  maps toolbar buttons with their functionality  ### 
class ToolbarProtocolHandler(unohelper.Base, XInitialization, XServiceInfo, XDispatchProvider):
    def __init__(self, ctx, *args):
        self.ctx = ctx
        pass
    
    # XInitialization
    def initialize(self, args):
        if len(args) > 0:
            self.frame = args[0]
    
    # XServiceInfo
    def supportsService(self, name):
        return (name == "com.sun.star.frame.ProtocolHandler")
    def getImplementationName(self):
        return IMPL_NAME2
    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)
    
    # XDispatchProvider
    def queryDispatch(self, url, name, flag):
        #ctypes.windll.user32.MessageBoxW(0, str(url.Complete), "url.complete", 1)
        dispatch = None
        if url.Protocol == IMPL_NAME + ":":
            try:
                self.command = url.Complete
                if url.Complete.endswith("Ratio"):
                    dispatch = KeepRatioToggle()
                elif url.Complete.endswith("TitleDescButton"):
                    dispatch = TitleDescToggle(frames)
                elif url.Complete.endswith("CheckToolButton"):
                    dispatch = OpenCheckTool()
                elif url.Complete.endswith("MetaDataButton"):
                    dispatch = OpenMetaDataDialog(self.ctx, frames)
                elif url.Complete.endswith("TangramAppButton"):
                    dispatch = OpenTangramWorkstation(self.ctx, frames)
                elif url.Complete.endswith("BorderSpacingButton"):
                    dispatch = BorderSpacing(self.ctx, frames)
                frames.add_item(self, dispatch, self.ctx)
            except Exception as e:
                print(e)
                #ctypes.windll.user32.MessageBoxW(0, str(e), "dispatch error", 1)
        return dispatch
    
    def queryDispatches(self, descs):
        pass


###  create toolbar element  ###
def create_window(toolkit, parent, wType, service, wAttributes, wX, wY, wWidth, wHeight):
    try:
        rect = Rectangle(wX, wY, wWidth, wHeight)
        return toolkit.createWindow(
            WindowDescriptor(wType, service, parent, -1, rect, wAttributes))
    except Exception as e:
            print(e)


###################################################################################################
###  util functions                                                                             ###
###################################################################################################
        
def create_uno_service(serviceName):
    try:
        service_manager = uno.getComponentContext().ServiceManager
        service = service_manager.createInstanceWithContext(serviceName, uno.getComponentContext())
        return service
    except Exception as e:
            print(e)
    
def get_controller(frames):
    try:
        controller = frames.items[0].frame.getController() #service: DrawingDocumentDrawView
        return controller
    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "get controller error", 1)
        
def get_page(controller):
    try:
        page = controller.getCurrentPage() #services: ShapeCollection, GenericDrawPage, LinkTarget, LinkTargetSupplier, DrawPage (interface XComponent etc.)
        return page        
    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "get page error", 1)
        
def get_first_shape_in_selection(controller):
    try:
        selection = controller.getSelection()
        if not selection:
            #ctypes.windll.user32.MessageBoxW(0, no_selection, warning, 1)
            return
        shape = selection.getByIndex(0)
        if not shape:
            #ctypes.windll.user32.MessageBoxW(0, no_selection, warning, 1)
            return
        return shape
    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "get selection error", 1)
        
def get_filled_shape_of_group(group):
    try:
        i = 0
        shape = None
        while i < group.getCount():
            s = group.getByIndex(i)
            if s.getPropertyValue("FillStyle") == NONE: # TODO: was ist wenn unteres shape auch keine Füllung hat?
                i = i+1
            else:
                shape = s
                break                     
        return shape

    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "get filled shape of group error", 1)
        
def get_none_filled_shape_of_group(group):
    try:
        shape = None
        count = group.getCount()
        if count == 2:
            s1 = group.getByIndex(0)
            s2 = group.getByIndex(1)
            if s1.getSize() == s2.getSize() and s1.getPosition().X == s2.getPosition().X and s1.getPosition().Y == s2.getPosition().Y:
                if s1.getPropertyValue("FillStyle") == NONE: # TODO: was ist wenn unteres shape auch keine Füllung hat?
                    shape = s1    
                elif s2.getPropertyValue("FillStyle") == NONE:
                    shape = s2
        return shape

    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "get none filled shape of group error", 1)

### test if the shape is a border-spacing group or not ###
def is_border_spacing_group(shape):
    try:
        if shape.getShapeType() == "com.sun.star.drawing.GroupShape":
            group = shape
            if group.getCount() == 2:
                s1 = group.getByIndex(0)
                s2 = group.getByIndex(1)
                if s1.getSize() == s2.getSize() and s1.getPosition().X == s2.getPosition().X and s1.getPosition().Y == s2.getPosition().Y:
                    return True
        return False
    
    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "is_border_spacing_group error", 1)
        

### class representing an undo/redo history object ###            
class UndoRedo(unohelper.Base, XUndoAction):
    Title = ""
    
    def __init__(self, ctx, function, title, undo_shape, redo_shape, controller):
        self.ctx = ctx
        self.function = function
        self.Title = title
        self.undo_shape = undo_shape
        self.redo_shape = redo_shape
        self.controller = controller
        
    def undo(self):
        #ctypes.windll.user32.MessageBoxW(0, str(self.function), "function", 1)
        try:
            if self.function == "add_border_spacing":
                undo_action = BorderSpacing(self.ctx, frames)
                undo_action.delete_border_spacing(self.undo_shape)
                pass
            
            elif self.function == "apply_pattern":
                shape = self.undo_shape[0]
                fill_style = self.undo_shape[1]
                #ctypes.windll.user32.MessageBoxW(0, str(fill_style), "fill style", 1)
                fill_value = self.undo_shape[2]
                #ctypes.windll.user32.MessageBoxW(0, str(fill_value), "fill value", 1)
                shape.FillStyle = fill_style
                if fill_style == BITMAP:
                    shape.FillBitmap = fill_value
                elif fill_style == SOLID:
                    shape.FillColor = fill_value
                # TODO: handle other fill styles
                
            else:
                pass
                
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "undo error", 1)
    
    def redo(self): 
        try:
            if self.function == "add_border_spacing":
                # call again add_border_spacing function for the original shape #
                redo_action = BorderSpacing(self.ctx, frames)
                redo_action.add_border_spacing(self.redo_shape)
                pass
    
            elif self.function == "apply_pattern":
                shape = self.redo_shape[0]
                fill_value = self.redo_shape[1]
                if fill_value == None: # no_pattern
                    shape.FillStyle = SOLID
                    shape.FillColor = 16777215 # white
                else:
                    shape.FillStyle = BITMAP
                    shape.FillBitmap = fill_value
    
            else:
                pass
                
        except Exception as e:
            print(e)
            #ctypes.windll.user32.MessageBoxW(0, str(e), "redo error", 1)

### add item to undo/redo history ###
def add_to_undo_redo_history(ctx, function, title, undo_shape, redo_shape, controller):
    try:
        undo_redo_action = UndoRedo(ctx, function, title, undo_shape, redo_shape, controller)
        desktop = ctx.getServiceManager().createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        oDoc = desktop.getCurrentComponent()
        um = oDoc.getUndoManager()
        um.enterUndoContext(title)
        um.addUndoAction(undo_redo_action)
        um.leaveUndoContext()

    except Exception as e:
        print(e)
        #ctypes.windll.user32.MessageBoxW(0, str(e), "add to undo/redo error", 1)

        
### python init ###
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ToolbarController,
    IMPL_NAME,
    ("com.sun.star.frame.ToolbarController",),)
    
g_ImplementationHelper.addImplementation(
    ToolbarProtocolHandler,
    IMPL_NAME2,
    ("com.sun.star.frame.ProtocolHandler",),)

