import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkhtmlview import HTMLLabel
import markdown2


class NotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestion de Notes")

        # Répertoire par défaut pour les notes
        self.notes_dir = os.path.expanduser("~/Notes/")
        os.makedirs(self.notes_dir, exist_ok=True)  # Crée le dossier si inexistant

        self.notes = {}  # Dictionnaire pour stocker les chemins des notes avec leurs titres
        self.current_file = None  # Fichier actuellement ouvert
        self.loaded_content = ""  # Contenu actuel de la note chargée
        self.is_markdown_mode = False  # Mode d'affichage actuel (Markdown ou texte brut)
        self.search_in_content = tk.BooleanVar()  # État de la checkbox "Recherche dans le contenu"

        # PanedWindow pour permettre la séparation déplaçable
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Cadre pour la recherche et l'arborescence
        self.tree_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.tree_frame, weight=1)

        # Ligne de recherche
        self.search_frame = tk.Frame(self.tree_frame)
        self.search_frame.pack(fill=tk.X)

        self.search_entry = tk.Entry(self.search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, pady=5)
        self.search_entry.bind("<KeyRelease>", self.filter_tree)

        self.content_search_checkbox = tk.Checkbutton(
            self.search_frame, text="Chercher dans les notes", variable=self.search_in_content, command=self.filter_tree
        )
        self.content_search_checkbox.pack(side=tk.LEFT, padx=5)

        # Treeview pour afficher l'arborescence
        self.tree = ttk.Treeview(self.tree_frame)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.handle_note_selection)

        # Zone de texte et boutons dans un cadre à droite
        self.editor_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.editor_frame, weight=2)

        self.text_editor = tk.Text(self.editor_frame, wrap="word", width=50, height=20)
        self.text_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_editor.bind("<Control-Return>", lambda event: self.save_note())  # Enregistrer avec Ctrl+Entrée

        # Boutons sous l'éditeur
        self.buttons_frame = tk.Frame(self.editor_frame)
        self.buttons_frame.pack(fill=tk.X, pady=5)

        self.save_button = tk.Button(
            self.buttons_frame, text="Enregistrer la note", command=self.save_note
        )
        self.save_button.pack(side=tk.LEFT, padx=5)

        self.toggle_button = tk.Button(
            self.buttons_frame, text="Activer le rendu Markdown", command=self.toggle_markdown_mode
        )
        self.toggle_button.pack(side=tk.LEFT, padx=5)

        # Widget pour afficher le contenu Markdown
        self.markdown_view = HTMLLabel(self.editor_frame, width=50, height=20, background="white", html="")
        self.markdown_view.pack_forget()  # Caché par défaut

        self.notification_label = tk.Label(self.root, text="", fg="green", bg="lightyellow")
        self.notification_label.pack_forget()  # Notification cachée par défaut

        self.refresh_tree()

        # Ajout des raccourcis clavier
        self.root.bind("<Control-Tab>", self.toggle_focus)
        self.root.bind("<Control-f>", self.focus_search)

    def refresh_tree(self):
        """Recharge l'arborescence des fichiers et dossiers."""
        self.tree.delete(*self.tree.get_children())
        self.notes.clear()  # Réinitialise la liste des notes

        # Ajoute le répertoire racine
        root_node = self.tree.insert("", "end", text=self.notes_dir, open=True, values=[self.notes_dir])
        self.populate_tree(root_node, self.notes_dir)

    def populate_tree(self, parent, directory):
        """Ajoute les sous-dossiers et fichiers à l'arborescence."""
        for entry in os.listdir(directory):
            entry_path = os.path.join(directory, entry)
            if os.path.isdir(entry_path):
                # Ajouter un dossier
                folder_node = self.tree.insert(parent, "end", text=entry, open=False, values=[entry_path])
                self.populate_tree(folder_node, entry_path)  # Récursivité
            elif entry.endswith(".md"):
                # Ajouter un fichier Markdown
                self.tree.insert(parent, "end", text=entry, values=[entry_path])
                self.notes[entry] = entry_path  # Stocker pour la recherche

    def filter_tree(self, event=None):
        """Filtre les notes affichées en fonction de la recherche."""
        query = self.search_entry.get().strip().lower()
        self.tree.delete(*self.tree.get_children())  # Efface le contenu actuel

        if not query:
            # Si la recherche est vide, recharge tout
            self.refresh_tree()
        else:
            # Recherche dans les dossiers et notes
            for root, dirs, files in os.walk(self.notes_dir):
                for directory in dirs:
                    if query in directory.lower():
                        dir_path = os.path.join(root, directory)
                        self.tree.insert("", "end", text=directory, values=[dir_path])
                for file in files:
                    if file.endswith(".md"):
                        file_path = os.path.join(root, file)
                        if query in file.lower():
                            self.tree.insert("", "end", text=file, values=[file_path])
                        elif self.search_in_content.get() and self.search_in_file(file_path, query):
                            self.tree.insert("", "end", text=file, values=[file_path])

    def search_in_file(self, filepath, query):
        """Recherche une chaîne de caractères dans un fichier."""
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
                if query in content.lower():
                    return True
        except Exception as e:
            print(f"Erreur lors de la lecture du fichier {filepath}: {e}")
        return False

    def handle_note_selection(self, event):
        """Gère la sélection d'une autre note avec un avertissement si la note actuelle a été modifiée."""
        selected_item = self.tree.selection()
        if not selected_item:
            return

        file_path = self.tree.item(selected_item[0], "values")[0]

        # Vérifie si la note a été modifiée
        current_content = self.text_editor.get("1.0", tk.END).strip()
        if current_content != self.loaded_content:
            response = messagebox.askyesnocancel(
                "Note modifiée",
                "Vous avez des modifications non enregistrées.\n"
                "Voulez-vous enregistrer avant de changer de note ?"
            )
            if response is None:  # Annuler
                return
            elif response:  # Oui, enregistrer
                self.save_note()
            # Si non, rétablir les changements (ne rien faire ici)

        self.load_selected_note(file_path)

    def load_selected_note(self, file_path):
        """Charge une note dans l'éditeur ou le widget Markdown."""
        if os.path.isfile(file_path) and file_path.endswith(".md"):
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            self.loaded_content = content  # Mettre à jour le contenu chargé
            self.current_file = file_path
            self.root.title(f"Gestion de Notes - {os.path.basename(file_path)}")

            if self.is_markdown_mode:
                html_content = markdown2.markdown(content)
                self.markdown_view.set_html(html_content)
                self.markdown_view.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                self.text_editor.pack_forget()
            else:
                self.text_editor.delete("1.0", tk.END)
                self.text_editor.insert(tk.END, content)
                self.text_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                self.markdown_view.pack_forget()

    def save_note(self):
        """Enregistre le contenu de l'éditeur dans le fichier sélectionné."""
        if not self.current_file:
            return

        content = self.text_editor.get("1.0", tk.END).strip()
        with open(self.current_file, "w", encoding="utf-8") as file:
            file.write(content)

        self.loaded_content = content  # Mettre à jour le contenu chargé
        self.show_notification(f"Note enregistrée : {os.path.basename(self.current_file)}")

    def show_notification(self, message):
        """Affiche une notification temporaire."""
        self.notification_label.config(text=message)
        self.notification_label.pack(fill=tk.X, pady=5)
        self.root.after(2000, lambda: self.notification_label.pack_forget())

    def toggle_markdown_mode(self):
        """Bascule entre le mode édition Markdown et le mode rendu."""
        self.is_markdown_mode = not self.is_markdown_mode
        self.toggle_button.config(
            text="Activer l'édition Texte" if self.is_markdown_mode else "Activer le rendu Markdown"
        )
        if self.current_file:
            self.load_selected_note(self.current_file)

    def toggle_focus(self, event):
        """Bascule le focus entre la liste des dossiers et l'éditeur de texte."""
        if self.tree.focus_get() == self.tree:
            self.text_editor.focus_set()
        else:
            self.tree.focus_set()

    def focus_search(self, event):
        """Met le focus sur le champ de recherche."""
        self.search_entry.focus_set()
        return "break"  # Empêche le comportement par défaut


if __name__ == "__main__":
    root = tk.Tk()
    app = NotesApp(root)
    root.mainloop()
