Unterschiede bei der Entwicklung von Python Extensions (Open Office vs. Libre Office)
-------------------------------------------------------------------------------------

1) Ausgabefenster für's Debuggen:

1a) für Open Office --> MessageBoxA
1b) für Libre Office --> MessageBoxW

z.B. ctypes.windll.user32.MessageBoxW(0, str("Message"), "Heading", 1)



2) Addons.xcu Datei:

2a) Open Office benötigt einen ToolBarItems Knoten
2b) bei Libre Office darf dieser Knoten nicht vorhanden sein