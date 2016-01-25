REM  *****  BASIC  *****

Dim Doc As Object			'whole document'
Dim Page As Object			'single page'
Dim Pages As Object			'all pages of the document'
Dim Str(100,2) As String 	'heading level, title, description  if level -1 it is text
Dim Position As String 

Sub Main
	Position = 0
	Doc = ThisComponent
	Pages = Doc.getDrawPages()
	Dim sr As String
	Dim sr1 As String		
	For I = 0 To Pages.Count - 1
		Page = Pages(I)
		If Page.hasElements Then			' single page of whole document			
			GetAllShapesOfPage(Page,1)
		End If	
	Next I
	Write2NewDocument()
End Sub

Sub GetAllShapesOfPage(Page as Object, HeadingLevel as Integer)
	For J = 0 To Page.Count - 1   	' parent
		child = Page(J)
		If child.getElementType().Name = "com.sun.star.drawing.XShape" Then					
			AddToShapes(child,HeadingLevel)
			If child.Count > 0 Then			
				GetAllShapesOfPage(child,HeadingLevel+1)
			End If
		End If
	Next J
End Sub


Sub AddToShapes(element as Object, HeadingLevel as Integer)
	Str(Position, 0 ) = CStr(HeadingLevel)
	Str(Position, 1 ) = CStr(element.getPropertyValue("Title"))
	Str(Position, 2 ) = CStr(element.getPropertyValue("Description"))
	Position = Position + 1		
End Sub

Dim Dummy()
Dim URL As String
Dim Doc As Object

Sub Write2NewDocument
	Dim oText As Variant
	Dim out As String
	Url = "private:factory/swriter"
	Doc = StarDesktop.loadComponentFromURL(URL, "_blank", 0, Dummy())
	For I = 0 To UBound(Str)
		If Len(Str(I,1)) > 0 Then
			out = out & "Headinglevel " &Str(I,0) &" " &Str(I,1) &"\n" 
			out = out & Str(I,2) &"\n"
		End If
	Next I

	oText = Doc.getText()
	oText.setString(out)
	
End Sub
