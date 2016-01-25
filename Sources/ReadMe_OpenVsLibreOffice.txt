Unterschiede bei der Entwicklung von Python Extensions (Open Office vs. Libre Office)
-------------------------------------------------------------------------------------

1) Ausgabefenster f�r's Debuggen:

1a) f�r Open Office --> MessageBoxA
1b) f�r Libre Office --> MessageBoxW

z.B. ctypes.windll.user32.MessageBoxW(0, str("Message"), "Heading", 1)



2) Addons.xcu Datei:

2a) Open Office ben�tigt einen ToolBarItems Knoten
2b) bei Libre Office darf dieser Knoten nicht vorhanden sein