"""Fenêtre principale de l’application."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker, EditionCleanupWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView
from .profile_navigation import ProfileNavigationMixin
from .preview_office import PreviewOfficeMixin
from .remote_operations import RemoteOperationsMixin
from .transfers import TransfersMixin
from .folder_operations import FolderOperationsMixin

class MainWindow(
    ProfileNavigationMixin,
    PreviewOfficeMixin,
    RemoteOperationsMixin,
    TransfersMixin,
    FolderOperationsMixin,
    QMainWindow,
):
    def __init__(self, vault_path, master_password, vault_data):
        super().__init__()

        self.vault_path = vault_path
        self.master_password = master_password
        self.vault_data = vault_data
        self.profile = self.get_profile()
        self.url_stack = []

        # Références conservées pendant le téléchargement
        self.download_worker = None
        self.download_dialog = None
        self.upload_worker = None
        self.upload_dialog = None
        self.multi_upload_worker = None
        self.multi_upload_dialog = None
        self.multi_download_worker = None
        self.multi_download_dialog = None
        self.delete_worker = None
        self.delete_dialog = None
        self.transfer_worker = None
        self.transfer_dialog = None
        self.preview_worker = None
        self.preview_progress_dialog = None
        self.preview_item_name = ""
        self.transfer_action_label = "Opération WebDAV"
        self.office_edit_worker = None
        self.new_office_worker = None
        self.office_edit_progress_dialog = None
        self.edition_cleanup_worker = None

        # Presse-papiers interne à Nextcloud Explorer.
        self.clipboard_items = []
        self.clipboard_mode = None
        self.clear_clipboard_after_transfer = False
        self.multi_download_skipped = 0
        
        self.setWindowTitle("Nextcloud Explorer")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        
        # Barre latérale
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 16)
        side.setSpacing(7)

        # Identité de l'application
        brand = QLabel("☁  Nextcloud Explorer")
        brand.setObjectName("sectionTitle")
        side.addWidget(brand)
        side.addSpacing(8)

        # --------------------------------------------------
        # ORDINATEUR : arborescence réelle de Windows
        # --------------------------------------------------
        local_label = QLabel("ORDINATEUR")
        local_label.setObjectName("muted")
        side.addWidget(local_label)

        self.local_model = QFileSystemModel(self)
        self.local_model.setFilter(
            QDir.Filter.AllEntries
            | QDir.Filter.NoDotAndDotDot
            | QDir.Filter.Drives
        )
        self.local_model.setRootPath("")

        self.local_tree = LocalDropTreeView()
        self.local_tree.setObjectName("localTree")
        self.local_tree.setModel(self.local_model)
        self.local_tree.setRootIndex(self.local_model.index(""))
        self.local_tree.setHeaderHidden(True)
        self.local_tree.setIndentation(15)
        self.local_tree.setAnimated(True)
        self.local_tree.setUniformRowHeights(True)
        self.local_tree.setMinimumHeight(150)

        # Afficher uniquement les noms des dossiers et des lecteurs
        for column in range(1, self.local_model.columnCount()):
            self.local_tree.hideColumn(column)
        self.local_tree.remote_items_dropped.connect(
            self.download_dropped_to_local
        )
        side.addWidget(self.local_tree, 1)

        # Séparateur visuel
        separator = QFrame()
        separator.setObjectName("sidebarSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        side.addWidget(separator)

        # --------------------------------------------------
        # NEXTCLOUD : conserver l'arborescence existante
        # --------------------------------------------------
        nav_label = QLabel("MON NEXTCLOUD")
        nav_label.setObjectName("muted")
        side.addWidget(nav_label)

        self.home_button = QPushButton("☁   Mon NEXTCLOUD")
        self.home_button.setObjectName("navButton")
        self.home_button.setCheckable(True)
        self.home_button.setChecked(True)
        self.home_button.clicked.connect(self.go_home)
        side.addWidget(self.home_button)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemExpanded.connect(self.load_tree_children)
        self.tree.itemClicked.connect(self.tree_item_clicked)
        side.addWidget(self.tree, 2)

        self.tree_root = None

        # Compte et connexion
        self.settings_button = QPushButton("⚙   Compte et connexion")
        self.settings_button.setObjectName("navButton")
        self.settings_button.clicked.connect(self.configure_profile)
        side.addWidget(self.settings_button)

        self.account_label = QLabel("●  Non connecté")
        self.account_label.setObjectName("muted")
        self.account_label.setWordWrap(True)
        side.addWidget(self.account_label)

        root.addWidget(sidebar)


        # Zone principale
        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(26, 22, 26, 18)
        main.setSpacing(15)
        root.addWidget(content, 1)

        top = QHBoxLayout()
        heading_box = QVBoxLayout()

        heading = QLabel("Mes fichiers")
        heading.setObjectName("appTitle")
        heading_box.addWidget(heading)

        self.subtitle = QLabel("Tes documents, accessibles depuis Nextcloud")
        self.subtitle.setObjectName("muted")
        heading_box.addWidget(self.subtitle)

        top.addLayout(heading_box)
        top.addStretch()

        self.upload_button = QPushButton("↑  Importer des fichiers")
        self.upload_button.setObjectName("primary")
        self.upload_button.clicked.connect(self.import_file)
        top.addWidget(self.upload_button)

        self.mkdir_button = QPushButton("+  Nouveau dossier")
        self.mkdir_button.clicked.connect(self.create_folder)
        top.addWidget(self.mkdir_button)

        self.refresh_button = QPushButton("↻  Actualiser")
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)

        main.addLayout(top)

        # Chemin courant et navigation
        path_bar = QHBoxLayout()
        path_bar.setSpacing(8)

        self.back_button = QPushButton("←")
        self.back_button.setToolTip("Dossier parent")
        self.back_button.setFixedWidth(42)
        self.back_button.clicked.connect(self.go_up)
        path_bar.addWidget(self.back_button)

        self.path_label = QLabel("Aucun compte configuré")
        self.path_label.setObjectName("muted")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_bar.addWidget(self.path_label, 1)

        main.addLayout(path_bar)

        # Tableau de fichiers
        self.table = DragDropTableWidget()
        self.table.local_files_dropped.connect(
            self.upload_dropped_to_remote
        )
        self.table.setHorizontalHeaderLabels(["Nom", "Taille", "Modifié le", "Type"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        self.table.itemDoubleClicked.connect(self.open_item)
        main.addWidget(self.table, 1)

        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("status")
        main.addWidget(self.status_label)

        # Connexion initiale
        if self.profile:
            self.url_stack = [self.profile["url"]]
            self.rebuild_tree()
            self.account_label.setText(
                f"●  Connecté à Nextcloud\n{self.profile['username']}"
            )
            self.refresh()
            self.start_edition_cleanup()
        else:
            self.path_label.setText("Configure ton compte pour commencer")
            self.status_label.setText(
                "Aucun compte configuré. Ouvre « Compte et connexion »."
            )


    def start_edition_cleanup(self):
        """Compare les copies d'édition au serveur sans bloquer l'interface."""
        if not self.profile:
            return
        if (
            self.edition_cleanup_worker is not None
            and self.edition_cleanup_worker.isRunning()
        ):
            return

        self.edition_cleanup_worker = EditionCleanupWorker(self.profile, self)
        self.edition_cleanup_worker.completed.connect(
            self.edition_cleanup_completed
        )
        self.edition_cleanup_worker.start()

    def edition_cleanup_completed(self, removed, kept):
        if removed:
            self.status_label.setText(
                f"Nettoyage des éditions : {removed} copie(s) identique(s) au serveur supprimée(s)."
            )
