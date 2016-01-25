import unohelper
import uno
import subprocess
import ctypes
import os
import sys
import string


# a UNO struct later needed to create a document
from com.sun.star.lang import typeOfXComponent
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
from com.sun.star.text.TextContentAnchorType import AS_CHARACTER
from com.sun.star.awt import Size
from com.sun.star.awt.WindowClass import SIMPLE

from com.sun.star.lang import XMain

startHeadingLevel = 1
arrayImageData = []

def exportImageData2WriterDocument():
    """Extract alle image data and create a writer document"""

    global arrayElement
    ctx = uno.getComponentContext()
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext( "com.sun.star.frame.Desktop",ctx)
    oDoc = desktop.getCurrentComponent()
    pages = oDoc.getDrawPages()
    # open a writer document
    # doc = desktop.loadComponentFromURL( "private:factory/swriter","_blank", 0, () )

    # text = doc.Text
    # cursor = text.createTextCursor()
    # text.insertString( cursor, "The first line in the newly created text document.\n", 0 )
    # text.insertString( cursor, "Now we are in the second line\n" , 0 )
    for index in range(pages.Count):
    	page = pages.getByIndex(index)
    	if page.hasElements():
    		getAllShapesFromElement(page, startHeadingLevel)
    write2Document(arrayImageData,desktop)

def getAllShapesFromElement(element, headingLevel):
	for index in range(element.Count):
		child = element.getByIndex(index)
		if child.getElementType() == uno.getTypeByName("com.sun.star.drawing.XShape"):
			arrayImageData.append([headingLevel, child.getPropertyValue("Title"),child.getPropertyValue("Description")])
			if child.Count > 0:
				getAllShapesFromElement(child, headingLevel+1)

def write2Document(array, desktop):
	doc = desktop.loadComponentFromURL( "private:factory/swriter","_blank", 0, () )
	text = doc.Text
	cursor = text.createTextCursor()
	cursor.setPropertyValue( "ParaStyleName", "Heading 1")
	text.insertString( cursor, "Bildbeschreibungen" , 0 )
	text.insertControlCharacter( cursor, PARAGRAPH_BREAK, 0 )
	#ctypes.windll.user32.MessageBoxW(0, str(array), "add border spacing error", 1)
	for entry in array:
		#ctypes.windll.user32.MessageBoxW(0, str(entry), "add border spacing error", 1)
		headingLevel = "Heading " + str(entry[0])
		headingContent = entry[1]
		paraContent = entry[2]
		# write content
		text.insertControlCharacter( cursor, PARAGRAPH_BREAK, 0 )
		cursor.setPropertyValue( "ParaStyleName", headingLevel)
		text.insertString( cursor, headingContent , 0 )
		text.insertControlCharacter( cursor, PARAGRAPH_BREAK, 0 )
		cursor.setPropertyValue( "ParaStyleName", "Text body")
		text.insertString( cursor, paraContent , 0 )





