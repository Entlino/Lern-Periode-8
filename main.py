import tkinter as tk  # GUI-Bibliothek
from tkinter import ttk  # Modernere Widgets für Tkinter
import yfinance as yf  # Bibliothek zum Abrufen von Finanzdaten


class FinanceApp:
    def __init__(self, root):
        """
        Konstruktor für die Finanz-App. Initialisiert das Fenster und die Widgets.
        """
        self.root = root
        self.root.title("Finanzdaten App")
        self.root.geometry("600x400")
        self.root.configure(bg="#2e2e2e")  # Dunkler Hintergrund

        # Titel
        self.title_label = tk.Label(root, text="Aktienkursanzeige", font=("Arial", 18, "bold"), bg="#2e2e2e",
                                    fg="#ffffff")
        self.title_label.pack(pady=30)

        # Eingabe für das Tickersymbol
        self.symbol_label = tk.Label(root, text="Gib ein Tickersymbol ein (z. B. AAPL, TSLA):", font=("Arial", 12),
                                     bg="#2e2e2e", fg="#ffffff")
        self.symbol_label.pack(pady=5)

        self.symbol_entry = tk.Entry(root, width=30, font=("Arial", 12), borderwidth=2, relief="solid", fg="#ffffff",
                                     bg="#3a3a3a")
        self.symbol_entry.pack(pady=10)

        # Button zum Abrufen der Daten
        self.fetch_button = ttk.Button(root, text="Daten abrufen", command=self.fetch_data, style="TButton")
        self.fetch_button.pack(pady=20)

        # Label für das Ergebnis
        self.result_label = tk.Label(root, text="Hier wird der Kurs angezeigt...", font=("Arial", 14), bg="#2e2e2e",
                                     fg="#ffffff")
        self.result_label.pack(pady=20)

        # Automatische Aktualisierung: Checkbox
        self.auto_update = tk.BooleanVar()
        self.auto_update_check = ttk.Checkbutton(
            root, text="Automatisch alle 10 Sekunden aktualisieren", variable=self.auto_update,
            command=self.toggle_auto_update, style="TCheckbutton"
        )
        self.auto_update_check.pack(pady=10)

        # Timer für automatische Updates
        self.update_interval = 10000  # 10 Sekunden in Millisekunden
        self.auto_update_job = None

        # Style für Button und andere Widgets
        self.style = ttk.Style()
        self.style.configure("TButton", padding=8, relief="flat", background="#4CAF50", foreground="white",
                             font=("Arial", 12, "bold"))
        self.style.map("TButton", background=[('active', '#45a049')])

        self.style.configure("TCheckbutton", font=("Arial", 12), foreground="white", background="#2e2e2e", padding=5)

    def fetch_data(self):
        """
        Holt den aktuellen Kurs des eingegebenen Tickersymbols und zeigt ihn in der GUI an.
        """
        symbol = self.symbol_entry.get().strip()  # Eingabe vom Benutzer
        if not symbol:
            self.result_label.config(text="Bitte gib ein gültiges Tickersymbol ein.")
            return

        try:
            # Abrufen der Daten
            stock = yf.Ticker(symbol)
            hist_data = stock.history(period="1d")

            # Überprüfen, ob Daten vorhanden sind
            if hist_data.empty:
                self.result_label.config(text=f"Keine Daten für {symbol.upper()} gefunden.")
                return

            # Abrufen des letzten Schlusspreises
            price = hist_data['Close'].iloc[-1]
            self.result_label.config(text=f"Aktueller Kurs von {symbol.upper()}: {price:.2f} USD")
        except Exception as e:
            # Fehlerbehandlung
            self.result_label.config(text="Fehler beim Abrufen der Daten.")
            print(f"Error: {e}")

    def toggle_auto_update(self):
        """
        Aktiviert oder deaktiviert die automatische Aktualisierung.
        """
        if self.auto_update.get():
            self.start_auto_update()
        else:
            self.stop_auto_update()

    def start_auto_update(self):
        """
        Startet den Timer für die automatische Aktualisierung.
        """
        self.fetch_data()  # Abrufen der Daten
        self.auto_update_job = self.root.after(self.update_interval, self.start_auto_update)

    def stop_auto_update(self):
        """
        Stoppt den Timer für die automatische Aktualisierung.
        """
        if self.auto_update_job:
            self.root.after_cancel(self.auto_update_job)
            self.auto_update_job = None


# Hauptprogramm
if __name__ == "__main__":
    root = tk.Tk()
    app = FinanceApp(root)
    root.mainloop()
