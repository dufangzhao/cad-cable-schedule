# -*- coding: utf-8 -*-
"""从离线版 LISP 派生菜单版 LISP，并追加菜单命令与设置对话框逻辑。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "templates" / "cable-summary-base.lsp"   # 基座模板（构建输入，不是交付物）
DST = ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary-cad.lsp"

EXTRA = r"""

;; ---------- menu edition: settings file ----------
;; Settings live in the same ini as runner/project, so the whole cad-plugin folder
;; can be copied to another machine together with its settings.

(defun cblsum:setting-file ()
  (if (and cblsum-ini (> (strlen cblsum-ini) 0))
    cblsum-ini
    (if cblsum-config cblsum-config (findfile "cable-summary.ini"))))

(defun cblsum:ini-set (key value / fh line lines found)
  "Rewrite one key in the ini, keeping every other line untouched."
  (setq fh (cblsum:setting-file))
  (if (null fh)
    nil
    (progn
      (setq lines (list) found nil)
      (setq f (open fh "r"))
      (if f
        (progn
          (while (setq line (read-line f))
            (if (= 0 (vl-string-search (strcat key "=") line))
              (progn (setq lines (append lines (list (strcat key "=" value))) found T))
              (setq lines (append lines (list line)))))
          (close f)))
      (if (null found) (setq lines (append lines (list (strcat key "=" value)))))
      (setq f (open fh "w"))
      (if f
        (progn
          (foreach line lines (write-line line f))
          (close f)
          T)
        nil))))

;; Default file name offered when the file name box is empty. The placeholder
;; below is replaced by the real Chinese default name while the menu edition is
;; built (tools/build_menu.py -> cblsum_i18n), because the derived LISP has to
;; stay pure ASCII. It matches what the engine calls a result with no --output-name.
(setq cblsum-default-name "cblsum-default-output-name.xlsx")

;; ---------- menu edition: pick the result file ----------
;; ONE box holds the whole result path (folder + file name). The browse dialog is
;; opened in "save file" mode and seeded with the current value, or - when the box
;; is still empty - with the desktop plus the default name, so the dialog itself
;; shows the user where an empty box would put the file.
;; Cancel must change nothing: getfiled returns nil then, and feeding that to
;; vl-filename-directory raised "bad argument type: stringp nil" inside the
;; dialog callback - an error there closes the whole dialog.
(defun cblsum:desktop-path (/ up)
  "Desktop folder with a trailing separator, or an empty string."
  (setq up (getenv "USERPROFILE"))
  (if (and up (> (strlen up) 0)) (strcat up "\\Desktop\\") ""))

;; Result file name shown in the dialog: the engine prepends the project/tag to
;; whatever name it is given, so the dialog must show the same thing - otherwise the
;; user picks "x.xlsx" and gets "TAG_x.xlsx" (or, before, filled in a tag and never
;; saw it anywhere).
(defun cblsum:default-name (/ tag)
  (setq tag (if (and *cblsum-project* (> (strlen *cblsum-project*) 0))
              (strcat *cblsum-project* "_")
              ""))
  (strcat tag cblsum-default-name))

(defun cblsum:pick-file (current / init picked)
  (setq init (if (and current (> (strlen current) 0))
               current
               (strcat (cblsum:desktop-path) (cblsum:default-name))))
  (setq picked (getfiled "Choose where the result file is saved" init "xlsx" 1))
  (if (and picked (> (strlen picked) 0)) picked current))

;; Fill the box with the current drawing folder plus the default file name.
(defun cblsum:use-dwg-folder ()
  (setq *cblsum-out-file* (strcat (getvar "DWGPREFIX") (cblsum:default-name)))
  (set_tile "out_dir" *cblsum-out-file*))

;; Browse button; cancel keeps the current value.
(defun cblsum:browse-folder ()
  ;; Use the tag currently typed in the dialog (the user may have just edited it),
  ;; so the suggested name matches what will really be written.
  (setq *cblsum-project* (cblsum:trim (get_tile "project")))
  (setq *cblsum-out-file* (cblsum:pick-file *cblsum-out-file*))
  (set_tile "out_dir" (if *cblsum-out-file* *cblsum-out-file* "")))

;; ---------- menu edition: settings dialog ----------
(defun cblsum:settings-load ()
  ;; ONE key describes the result: the full path. Empty means "desktop, and let
  ;; the engine name the file" - the same thing it does without --output.
  (setq *cblsum-out-file* (cblsum:ini-get "output_file" ""))
  (setq *cblsum-project*  (cblsum:ini-get "project" ""))
  ;; default OFF to match the engine: it only adds a timestamp when asked, and it
  ;; already keeps an existing file from being overwritten on its own
  (setq *cblsum-timestamp* (= (strcase (cblsum:ini-get "timestamp" "0")) "1"))
  (setq *cblsum-autopen*   (= (strcase (cblsum:ini-get "auto_open" "1")) "1")))

(defun c:CREATE_SETTINGS_DIALOG () (c:CABLE_SUM_SETTINGS))

;; ---------- menu edition: helpers for the dialog callbacks ----------
;; MEASURED on AutoCAD 2020: while a DCL dialog is open, injecting anything into
;; the command line (another program driving AutoCAD through ActiveX, for example)
;; makes AutoCAD terminate the dialog. The window can then be left behind as an
;; orphan while CMDACTIVE stays 8: the dialog ignores every window message -
;; WM_CLOSE, ESC, a click on Cancel, even a real mouse click - and AutoCAD has to
;; be restarted. So: never drive the command line while this dialog is up.
(defun cblsum:apply-dialog (/ dcl ok result)
  (setq dcl (cblsum:dcl-path))
  (if (null dcl)
    (progn
      (princ "\n[cable-sum-schedule] settings dialog needs the file: cable-summary-settings.dcl")
      nil)
    (progn
      (setq ok (load_dialog dcl))
      (if (< ok 0)
        (progn
          (princ (strcat "\n[cable-sum-schedule] cannot load dialog: " dcl))
          nil)
        (progn
          (if (new_dialog "cable_summary_settings" ok)
            (progn
              (cblsum:fill-dialog)
              (action_tile "browse" "(cblsum:browse-folder)")
              (action_tile "use_dwg_dir" "(cblsum:use-dwg-folder)")
              (action_tile "accept"
                "(cblsum:read-dialog)(done_dialog 1)")
              (action_tile "cancel" "(done_dialog 0)")
              (setq result (start_dialog))
              (unload_dialog ok)
              (if (= result -1)
                (princ "\n[cable-sum-schedule] the dialog was terminated by another command."))
              (= result 1))
            (progn (unload_dialog ok) nil)))))))

(defun cblsum:dcl-path (/ p base)
  "Absolute path of cable-summary-settings.dcl.
   The settings ini and the dcl live in the same folder, and the ini is found
   reliably (install.bat bakes its absolute path in, or it sits next to the
   drawing / in the support path), so the ini folder is the anchor. cblsum-home
   is only a fallback: measured on AutoCAD 2020 it is always nil, because
   AutoLISP cannot learn the path a file was loaded from."
  (setq p nil
        base (cblsum:setting-file))
  (if (and base (> (strlen base) 0))
    (setq p (strcat (cblsum:dir-of base) "cable-summary-settings.dcl")))
  (if (and (or (null p) (null (findfile p))) cblsum-home)
    (setq p (strcat (cblsum:dir-of cblsum-home) "cable-summary-settings.dcl")))
  (if (and p (findfile p)) p (findfile "cable-summary-settings.dcl")))

;; ONE box for everything about the result file. Empty = desktop + automatic
;; name, which is exactly what the engine does when it gets no --output.
(defun cblsum:fill-dialog ()
  (set_tile "out_dir" (if *cblsum-out-file* *cblsum-out-file* ""))
  (set_tile "project" (if *cblsum-project* *cblsum-project* ""))
  (set_tile "timestamp" (if *cblsum-timestamp* "1" "0"))
  (set_tile "auto_open" (if *cblsum-autopen* "1" "0")))

(defun cblsum:read-dialog ()
  (setq *cblsum-out-file* (cblsum:trim (get_tile "out_dir")))
  (setq *cblsum-project* (cblsum:trim (get_tile "project")))
  (setq *cblsum-timestamp* (= (get_tile "timestamp") "1"))
  (setq *cblsum-autopen*   (= (get_tile "auto_open") "1")))

(defun c:CABLE_SUM_SETTINGS (/ saved)
  (cblsum:load-config)
  (cblsum:settings-load)
  (if (cblsum:apply-dialog)
    (progn
      (cblsum:ini-set "output_file" *cblsum-out-file*)
      (cblsum:ini-set "project" *cblsum-project*)
      (cblsum:ini-set "timestamp" (if *cblsum-timestamp* "1" "0"))
      (cblsum:ini-set "auto_open" (if *cblsum-autopen* "1" "0"))
      (princ "\n[cable-sum-schedule] settings saved"))
    (princ "\n[cable-sum-schedule] settings unchanged"))
  (princ))

;; ---------- menu edition: open the result folder ----------
(defun c:CABLE_SUM_OPEN (/ dir res)
  (cblsum:load-config)
  (setq dir (cblsum:ini-get "last_folder" ""))
  (if (= dir "")
    (progn
      ;; the settings box may hold a full file path - this command opens its folder
      (setq res (cblsum:ini-get "output_file" ""))
      (if (and (/= res "") (= (strcase (vl-filename-extension res)) ".XLSX"))
        (setq dir (vl-filename-directory res))
        (setq dir res))))
  (if (= dir "") (setq dir (strcat (getenv "USERPROFILE") "\\Desktop")))
  (if (findfile (strcat dir "\\"))
    (progn
      (princ (strcat "\n[cable-sum-schedule] result folder: " dir))
      (startapp (strcat "explorer \"" dir "\"")))
    (princ "\n[cable-sum-schedule] no result folder yet - nothing to open."))
  (princ))

;; ---------- menu edition: self-check / about ----------
;; The menu item RUNS the self check instead of telling the user to run it: it starts
;; check.bat, which opens its own console window, prints the report and waits for a
;; key press - so the result stays readable and nothing depends on the AutoCAD command
;; line (the engine is built without a console, so its output has to go somewhere the
;; user can see).
(defun c:CABLE_SUM_CHECK (/ base bat exe)
  (cblsum:load-config)
  (setq base (cblsum:setting-file))
  (setq bat (if base (strcat (cblsum:dir-of base) "check.bat") nil)
        exe (if base (strcat (cblsum:dir-of base) "cable-summary.exe") nil))
  (cond
    ((and bat (findfile bat))
     (princ "\n[cable-sum-schedule] running the self check - read the window that just opened.")
     (startapp (strcat "\"" bat "\"")))
    ((and exe (findfile exe))
     (princ "\n[cable-sum-schedule] running the self check - read the window that just opened.")
     (startapp (strcat "cmd.exe /k \"" exe "\" --self-test")))
    (T
     (princ "\n[cable-sum-schedule] cannot find check.bat - run it from the cad-plugin folder.")))
  (princ))

(defun c:CABLE_SUM_ABOUT (/ r)
  (princ (strcat "\n[cable-sum-schedule] version " cblsum-version " (menu edition)"))
  (princ (strcat "\nconfig file: " (if (cblsum:setting-file) (cblsum:setting-file) "(not found)")))
  (setq r (cblsum:ini-get "runner" ""))
  (princ (strcat "\nengine     : " (if (= r "") "(not configured)" r)))
  (princ))

;; ---------- menu edition: load settings at startup ----------
(cblsum:settings-load)
(defun cblsum:menu-file (/ p)
  "Absolute path of cable-summary.cuix, looked up next to the plugin first."
  (if cblsum-home
    (progn
      (setq p (strcat (cblsum:dir-of cblsum-home) "cable-summary.cuix"))
      (if (findfile p) p (findfile "cable-summary.cuix")))
    (findfile "cable-summary.cuix")))

;; ---------- menu edition: build the menu with COM (main route, no .cuix) ----------
;; The menu is created from COM objects instead of a .cuix file: a hand-generated
;; .cuix could not be confirmed to load in AutoCAD 2020 (CUILOAD looked like it did
;; nothing), while every COM step below reports its own result, so a failure names
;; the step that failed instead of leaving the user to guess.
;; The menu group name is deliberately ASCII: it is never displayed and has to
;; survive on any Windows code page.

(setq cblsum-menu-group "CABLESUM")
(setq cblsum-menu-name "Cable Summary")

(defun cblsum:com (fun args)
  "Run one COM call defensively: a failure comes back as an error object."
  (vl-catch-all-apply fun args))

(defun cblsum:com-val (res)
  "Value of a COM call, nil when that call failed."
  (if (vl-catch-all-error-p res) nil res))

(defun cblsum:com-err (res)
  "Error text of a failed COM call, empty text when the call worked."
  (if (vl-catch-all-error-p res) (vl-catch-all-error-message res) ""))

(defun cblsum:menu-bar-of (app)
  "Menu bar of this AutoCAD session, nil when it cannot be read."
  "MenuBar is a property of the Application object - the menu bar is"
  "application-wide - so it has to be asked of the AutoCAD object itself."
  "Asking the drawing for it fails with: unknown name: MenuBar."
  (cblsum:com-val (cblsum:com 'vla-get-MenuBar (list app))))

(defun cblsum:menu-end-index (menu / n)
  "Index that appends: one past the last item, which is what AutoCAD documents."
  (setq n (cblsum:com-val (cblsum:com 'vla-get-Count (list menu))))
  (if (numberp n) (1+ n) 1))

(defun cblsum:menu-popup-find (menus / n i item nm hit)
  "Popup menu of the collection whose name is our menu name, or nil."
  (setq hit nil)
  (if menus
    (progn
      (setq n (cblsum:com-val (cblsum:com 'vla-get-Count (list menus))))
      (if (null n) (setq n 0))
      (setq i 0)
      (while (< i n)
        (setq item (cblsum:com-val (cblsum:com 'vla-Item (list menus i))))
        (if item
          (progn
            (setq nm (cblsum:com-val (cblsum:com 'vla-get-Name (list item))))
            (if (and nm (= (strcase nm) (strcase cblsum-menu-name)))
              (setq hit item))))
        (setq i (1+ i)))))
  hit)

(defun cblsum:menu-group-of (app / mgs grp res)
  "Menu group that hosts our menu: the CABLESUM group when it exists or can be"
  "created, otherwise the base menu group of this AutoCAD. The fallback exists"
  "because AutoCAD ActiveX cannot create empty menu groups; the base group is"
  "always there, so the menu still works in this session."
  (setq mgs (cblsum:com-val (cblsum:com 'vla-get-MenuGroups (list app))))
  (if (null mgs)
    (progn
      (princ "\n[cable-sum-schedule] cannot read the menu groups of this AutoCAD.")
      nil)
    (progn
      (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs cblsum-menu-group))))
      (if grp
        (princ (strcat "\n[cable-sum-schedule] existing menu group reused: " cblsum-menu-group))
        (progn
          (setq res (cblsum:com 'vla-Add (list mgs cblsum-menu-group)))
          (setq grp (cblsum:com-val res))
          (if grp
            (princ (strcat "\n[cable-sum-schedule] menu group created: " cblsum-menu-group))
            (princ (strcat "\n[cable-sum-schedule] cannot create the menu group "
                           cblsum-menu-group ": " (cblsum:com-err res))))))
      (if (null grp)
        (progn
          (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs "ACAD"))))
          (if (null grp)
            (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs 0)))))
          (if grp
            (progn
              (princ "\n[cable-sum-schedule] using the base menu group instead.")
              (princ "\n[cable-sum-schedule] this menu lasts for this AutoCAD session only."))
            (princ "\n[cable-sum-schedule] no menu group is available for the menu."))))
      grp)))

(defun cblsum:menu-append (menu label macro / res)
  "Append one command item at the end of the popup menu."
  (setq res (cblsum:com 'vla-AddMenuItem
                        (list menu (cblsum:menu-end-index menu) label macro)))
  (if (vl-catch-all-error-p res)
    (progn
      (princ (strcat "\n[cable-sum-schedule] cannot add the menu item "
                     label ": " (cblsum:com-err res)))
      nil)
    (progn
      (princ (strcat "\n[cable-sum-schedule] menu item added: " label))
      T)))

(defun cblsum:menu-append-sep (menu / res)
  "Append one separator at the end of the popup menu."
  (setq res (cblsum:com 'vla-AddSeparator (list menu (cblsum:menu-end-index menu))))
  (if (vl-catch-all-error-p res)
    (progn
      (princ (strcat "\n[cable-sum-schedule] cannot add the separator: " (cblsum:com-err res)))
      nil)
    (progn
      (princ "\n[cable-sum-schedule] separator added.")
      T)))

;; Measured on AutoCAD 2020: a menu macro assigned through ActiveX is sent to
;; the command line VERBATIM - the "^C^C^C" prefix is NOT translated into
;; cancels, and clicking such an item answers: unknown command "^C^C^C_CABLE_SUM".
;; The escape character itself (byte 27) is honored, so macros start with two
;; ESC bytes instead of the caret notation.
(defun cblsum:macro (cmd)
  (strcat (chr 27) (chr 27) "_" cmd " "))

(defun cblsum:menu-fill (menu)
  "The six commands and the two separators, in menu order."
  (cblsum:menu-append menu "Count Selected Cables" (cblsum:macro "CABLE_SUM"))
  (cblsum:menu-append-sep menu)
  (cblsum:menu-append menu "Settings..." (cblsum:macro "CABLE_SUM_SETTINGS"))
  (cblsum:menu-append menu "Open Result Folder" (cblsum:macro "CABLE_SUM_OPEN"))
  (cblsum:menu-append-sep menu)
  (cblsum:menu-append menu "Self Check" (cblsum:macro "CABLE_SUM_CHECK"))
  (cblsum:menu-append menu "About" (cblsum:macro "CABLE_SUM_ABOUT"))
  (cblsum:menu-append menu "Unload Menu" (cblsum:macro "CABLE_SUM_MENU_REMOVE"))
  T)

(defun cblsum:menu-bar-holds-p (bar / n i item nm found)
  "T when a popup menu with our name is already on the menu bar."
  (setq n (cblsum:com-val (cblsum:com 'vla-get-Count (list bar))))
  (if (null n) (setq n 0))
  (setq i 0
        found nil)
  (while (< i n)
    (setq item (cblsum:com-val (cblsum:com 'vla-Item (list bar i))))
    (if item
      (progn
        (setq nm (cblsum:com-val (cblsum:com 'vla-get-Name (list item))))
        (if (and nm (= (strcase nm) (strcase cblsum-menu-name)))
          (setq found T))))
    (setq i (1+ i)))
  found)

(defun cblsum:menu-bar-add (bar pop / n res)
  "Put the popup menu at the end of the menu bar, unless it is already there."
  (if (cblsum:menu-bar-holds-p bar)
    (progn
      (princ "\n[cable-sum-schedule] the menu is already on the menu bar.")
      T)
    (progn
      (setq n (cblsum:com-val (cblsum:com 'vla-get-Count (list bar))))
      (if (null n) (setq n 0))
      (setq res (cblsum:com 'vla-InsertInMenuBar (list pop n)))
      (if (vl-catch-all-error-p res)
        (setq res (cblsum:com 'vla-InsertInMenuBar (list pop (1+ n)))))
      (if (vl-catch-all-error-p res)
        (progn
          (princ (strcat "\n[cable-sum-schedule] cannot insert the menu into the menu bar: "
                         (cblsum:com-err res)))
          nil)
        (progn
          (princ "\n[cable-sum-schedule] menu added to the menu bar (look at the right end).")
          T)))))

(defun cblsum:menu-put-on-bar (app pop / bar)
  "Insert the popup menu into the menu bar of the active drawing."
  (setq bar (if app (cblsum:menu-bar-of app) nil))
  (if (null bar)
    (progn
      (princ "\n[cable-sum-schedule] cannot read the menu bar of this drawing.")
      nil)
    (cblsum:menu-bar-add bar pop)))

(defun cblsum:menu-popup-in-group (app group / mgs grp menus)
  "Popup menu with our name inside the given menu group, or nil."
  (setq mgs (cblsum:com-val (cblsum:com 'vla-get-MenuGroups (list app))))
  (if (null mgs)
    nil
    (progn
      (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs group))))
      (if (null grp)
        nil
        (progn
          (setq menus (cblsum:com-val (cblsum:com 'vla-get-Menus (list grp))))
          (cblsum:menu-popup-find menus))))))

(defun cblsum:menu-from-cuix (app / cuix mgs grp res pop)
  "Fallback route: load cable-summary.cuix as a partial menu and put its popup"
  "menu on the menu bar. vla-InsertInMenuBar belongs to the PopupMenu object -"
  "the first version of this command called it on the menu bar, which has no"
  "such method, and that is why the menu never showed up."
  (setq cuix (cblsum:menu-file))
  (cond
    ((or (null cuix) (null (findfile cuix)))
     (princ "\n[cable-sum-schedule] cable-summary.cuix not found next to the plugin.")
     nil)
    (T
     (princ (strcat "\n[cable-sum-schedule] menu file: " cuix))
     (setq mgs (cblsum:com-val (cblsum:com 'vla-get-MenuGroups (list app))))
     (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs cblsum-menu-group))))
     (if grp
       (princ (strcat "\n[cable-sum-schedule] menu group already loaded: " cblsum-menu-group))
       (progn
         ;; :vlax-false loads the file as a PARTIAL menu. Loading it as the base
         ;; menu would replace every menu of the running AutoCAD session.
         (setq res (cblsum:com 'vla-Load (list mgs cuix :vlax-false)))
         (setq grp (cblsum:com-val res))
         (if grp
           (princ (strcat "\n[cable-sum-schedule] menu group loaded: " cblsum-menu-group))
           (princ (strcat "\n[cable-sum-schedule] cannot load the menu file: "
                          (cblsum:com-err res))))))
     (setq pop (if grp (cblsum:menu-popup-in-group app cblsum-menu-group) nil))
     (cond
       ((null pop)
        (princ (strcat "\n[cable-sum-schedule] the loaded menu file has no menu named: "
                       cblsum-menu-name))
        nil)
       (T
        (cblsum:menu-put-on-bar app pop))))))

(defun c:CABLE_SUM_MENU (/ app grp menus pop res ok)
  (cblsum:load-config)
  (princ "\n[cable-sum-schedule] building the menu with COM, no menu file needed...")
  (vl-load-com)
  (setq app (vlax-get-acad-object))
  (if (null app)
    (princ "\n[cable-sum-schedule] COM is not available in this AutoCAD.")
    (progn
      (setq ok nil)
      (setq grp (cblsum:menu-group-of app))
      (if grp
        (progn
          (setq menus (cblsum:com-val (cblsum:com 'vla-get-Menus (list grp))))
          (setq pop (cblsum:menu-popup-find menus))
          (if pop
            (progn
              (princ (strcat "\n[cable-sum-schedule] existing popup menu reused: " cblsum-menu-name))
              ;; an empty popup is a leftover from an interrupted run: fill it
              (setq res (cblsum:com 'vla-get-Count (list pop)))
              (if (or (vl-catch-all-error-p res) (= 0 res))
                (cblsum:menu-fill pop)))
            (progn
              (setq res (cblsum:com 'vla-Add (list menus cblsum-menu-name)))
              (setq pop (cblsum:com-val res))
              (if pop
                (progn
                  (princ (strcat "\n[cable-sum-schedule] popup menu created: " cblsum-menu-name))
                  (cblsum:menu-fill pop))
                (princ (strcat "\n[cable-sum-schedule] cannot create the popup menu: "
                               (cblsum:com-err res))))))
          (if pop
            (setq ok (cblsum:menu-put-on-bar app pop)))))
      ;; fallback route: only when the COM route produced no menu on the bar
      (if (null ok)
        (progn
          (princ "\n[cable-sum-schedule] the COM route did not finish - trying the menu file.")
          (setq ok (cblsum:menu-from-cuix app))))
      (if (null ok)
        (princ "\n[cable-sum-schedule] no menu was created.")
        (if (vl-catch-all-error-p (vl-catch-all-apply 'setvar (list "MENUBAR" 1)))
          (princ "\n[cable-sum-schedule] cannot switch the menu bar on.")
          (princ "\n[cable-sum-schedule] menu bar display is on (MENUBAR=1).")))))
  (princ))

;; Measured on AutoCAD 2020: (command "_.MENUUNLOAD" <name>) with a group name that
;; is not loaded aborts the whole Lisp evaluation. vl-catch-all-apply does NOT hold
;; it, and every form after it - the feedback princ included - is skipped. So
;; MENUUNLOAD is (a) called only after the group was found to exist and (b)
;; deliberately the LAST step of this command: by then the menu is already off the
;; menu bar, so a failure there cannot undo the real work.

(defun cblsum:menu-group-find (app group / mgs)
  "Menu group with this name, nil when this AutoCAD does not have it loaded."
  (setq mgs (cblsum:com-val (cblsum:com 'vla-get-MenuGroups (list app))))
  (if mgs
    (cblsum:com-val (cblsum:com 'vla-Item (list mgs group)))
    nil))

(defun c:CABLE_SUM_MENU_REMOVE (/ app bar pop res grp inbase)
  (vl-load-com)
  (setq app (vlax-get-acad-object))
  (if (null app)
    (princ "\n[cable-sum-schedule] COM is not available in this AutoCAD.")
    (progn
      ;; 1) the real job: take the menu off the menu bar. The menu lives either in
      ;;    its own CABLESUM group or in the base group (ACAD), so look in both.
      (setq inbase nil)
      (setq pop (cblsum:menu-popup-in-group app cblsum-menu-group))
      (if pop
        (princ "\n[cable-sum-schedule] popup menu found in the CABLESUM menu group.")
        (progn
          (setq pop (cblsum:menu-popup-in-group app "ACAD"))
          (if pop
            (progn
              (setq inbase T)
              (princ "\n[cable-sum-schedule] popup menu found in the base menu group (ACAD).")))))
      (cond
        ((null pop)
         (princ "\n[cable-sum-schedule] no cable summary menu is loaded."))
        ((null (setq bar (cblsum:menu-bar-of app)))
         (princ "\n[cable-sum-schedule] cannot read the menu bar of this drawing."))
        ((null (cblsum:menu-bar-holds-p bar))
         (princ "\n[cable-sum-schedule] the menu is not on the menu bar, so there is nothing to take off."))
        (T
         (setq res (cblsum:com 'vla-RemoveFromMenuBar (list pop)))
         (if (vl-catch-all-error-p res)
           (princ (strcat "\n[cable-sum-schedule] cannot take the menu off the menu bar: "
                          (cblsum:com-err res)))
           (princ "\n[cable-sum-schedule] menu taken off the menu bar."))))
      ;; 2) unload the group, but only when it exists (see the note above)
      (setq grp (cblsum:menu-group-find app cblsum-menu-group))
      (if grp
        (progn
          (princ "\n[cable-sum-schedule] unloading the menu group CABLESUM...")
          (setq res (vl-catch-all-apply 'command (list "_.MENUUNLOAD" cblsum-menu-group)))
          (if (vl-catch-all-error-p res)
            (princ (strcat "\n[cable-sum-schedule] MENUUNLOAD failed: " (cblsum:com-err res)))
            (princ "\n[cable-sum-schedule] MENUUNLOAD done.")))
        (progn
          (princ "\n[cable-sum-schedule] the CABLESUM menu group is not loaded, so there is nothing to unload.")
          (if inbase
            (princ "\n[cable-sum-schedule] the base menu group cannot be unloaded - the menu stays there and is reused next time."))))
      (princ "\n[cable-sum-schedule] to remove the plugin completely, run uninstall.bat in the plugin folder.")))
  (princ))

;; ---------- menu edition: build the menu as soon as this file is loaded ----------
;; AutoCAD loads this file at every start (official Autoloader: the bundle in
;; ApplicationPlugins declares it), and the load itself puts the menu on the menu
;; bar. Having the menu already is not an error - c:CABLE_SUM_MENU reuses it
;; instead of adding a second one - so APPLOADing the file by hand still works.
;; Wrapped in vl-catch-all-apply: a menu problem must never break the load.
(vl-catch-all-apply (function c:CABLE_SUM_MENU) nil)

"""

text = SRC.read_text(encoding="ascii")
text = text.replace("cblsum-version \"1.0.0-offline\"", "cblsum-version \"1.0.0-menu\"", 1)
text = text + EXTRA
if any(ord(c) > 127 for c in text):
    print("派生结果含非 ASCII，请检查 EXTRA"); raise SystemExit(1)
DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(text, encoding="ascii")
print(f"已生成 {DST.relative_to(ROOT)}  ({len(text)} 字符, 纯 ASCII)")
