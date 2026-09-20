;;; ============================================================================
;;; Cable schedule summary - AutoCAD plugin (offline edition)
;;;
;;; Usage: select the cable table(s) in the drawing, then run CABLE_SUM (alias CBLSUM)
;;;        The plugin exports the selected text, hands it to the launcher run.bat
;;;        (which prefers the bundled cable-summary.exe) and opens the result Excel.
;;;
;;; Notes: no server, no Python install, no network needed. The drawing is never
;;;        modified or saved by this plugin.
;;;
;;; Install: copy the whole cad-plugin folder anywhere on this machine, then
;;;          APPLOAD this file. Config lives in cable-summary.ini next to it and
;;;          is re-read on every run, so edits take effect without reloading.
;;;
;;; This file is intentionally PURE ASCII: AutoCAD reads LISP using the system
;;; ANSI code page, and non-ASCII bytes in a UTF-8 file can corrupt parsing on
;;; Chinese Windows. Keep all messages in ASCII.
;;; ============================================================================

(setq cblsum-version "1.0.0-menu"
      cblsum-config  nil
      cblsum-home    nil
      cblsum-ini     nil)   ; <<CBLSUM-INI>> install.bat bakes the absolute path here

(defun cblsum:cdr (code lst)
  "Safe cdr: return nil instead of erroring."
  (cdr (assoc code lst)))

(defun cblsum:num (v d)
  (if (numberp v) v d))

(defun cblsum:trim (s)
  (if s (vl-string-trim " \t\r\n" s) ""))

(defun cblsum:unescape (s)
  "Turn the pipe placeholder written by the engine back into newlines.
   The engine cannot put real newlines inside a value (AutoLISP reads the
   response file line by line), so it joins the lines with a pipe."
  (if s (vl-string-translate "|" "\n" s) ""))

(defun cblsum:dir-of (path / d)
  "Directory part of a path, with a trailing separator."
  (if path
    (progn
      (setq d (vl-filename-directory path))
      (if (and d (> (strlen d) 0))
        (strcat d "\\")
        ""))
    ""))

;; ---------- first-run bootstrap (official Autoloader bundle) ----------
;; A hand-copied bundle has no cable-summary.ini yet - that file is per-machine, because
;; it holds absolute paths. Instead of insisting on an install step, the first load writes
;; a minimal one next to this LISP. Only the plugin's own folder is touched; nothing else
;; on the machine (no acaddoc.lsp, no support folder) is modified.
(defun cblsum:bundle-contents (/ ad root dirs d hit)
  "Contents folder of the bundle this file came from, or nil when it is not installed."
  (setq ad (getenv "APPDATA"))
  (if (and ad (> (strlen ad) 0))
    (progn
      (setq root (strcat ad "\\Autodesk\\ApplicationPlugins\\"))
      (setq hit (strcat root "CableSummary.bundle\\Contents\\"))
      (if (findfile (strcat hit "cable-summary-cad.lsp"))
        hit
        ;; The folder was renamed (Explorer copy, "CableSummary (1).bundle", ...):
        ;; look for any *.bundle under ApplicationPlugins that carries our LISP.
        (progn
          (setq hit nil)
          (setq dirs (vl-directory-files root "*.bundle" 1))
          (foreach d dirs
            (if (and (null hit)
                     (findfile (strcat root d "\\Contents\\cable-summary-cad.lsp")))
              (setq hit (strcat root d "\\Contents\\"))))
          hit)))
    nil))

(defun cblsum:trusted-path-add (dir / cur)
  "Append dir to TRUSTEDPATHS so the unsigned plugin stops asking at startup."
  (if (and dir (> (strlen dir) 0))
    (progn
      (setq cur (getvar "TRUSTEDPATHS"))
      (if (vl-string-search (strcase dir) (strcase cur))
        nil
        (progn
          (setvar "TRUSTEDPATHS"
            (if (> (strlen (vl-string-right-trim ";" cur)) 0)
              (strcat (vl-string-right-trim ";" cur) ";" dir)
              dir))
          T)))))

(defun cblsum:ensure-config (/ dir ini fh)
  "Write a minimal cable-summary.ini next to the plugin when nothing is configured."
  (setq dir (cblsum:bundle-contents))
  (if (and dir
           (findfile (strcat dir "cable-summary-cad.lsp"))
           (null (findfile (strcat dir "cable-summary.ini"))))
    (progn
      (setq ini (strcat dir "cable-summary.ini")
            fh (open ini "w"))
      (if fh
        (progn
          (write-line "; Cable summary CAD plugin - written automatically on first load." fh)
          (write-line "; runner: absolute path of the summary engine." fh)
          (write-line (strcat "runner=" dir "cable-summary.exe") fh)
          (write-line "project=" fh)
          (write-line "extra_args=" fh)
          (close fh)
          (setq cblsum-ini ini
                cblsum-config ini)
          (princ "\n[cable-sum-schedule] first run: wrote cable-summary.ini next to the plugin.")
          (if (cblsum:trusted-path-add dir)
            (princ "\n[cable-sum-schedule] plugin folder added to TRUSTEDPATHS (no startup prompt)."))
          T)
        nil))
    nil))

;; Populate the candidate list. NOTE: cblsum-home stays nil in practice - AutoLISP
;; cannot learn the path this file was loaded from (there is no "this file" variable
;; and (findfile "cable-summary-cad.lsp") only searches the AutoCAD support path).
;; That is why install.bat bakes cblsum-ini in, and why every other lookup below
;; derives the plugin folder from an ini that was actually found.
(defun cblsum:candidates (/ l ini)
  (setq l (list)
        ini (strcat (getenv "USERPROFILE") "\\Desktop\\cable-summary.ini"))
  ;; 0) absolute path baked in by install.bat (most reliable - no searching involved)
  (if (and cblsum-ini (> (strlen cblsum-ini) 0))
    (setq l (cons cblsum-ini l)))
  (if cblsum-home (setq l (cons (strcat (cblsum:dir-of cblsum-home) "cable-summary.ini") l)))
  (setq l (cons (strcat (getvar "DWGPREFIX") "cable-summary.ini") l))
  (if (setq hit (findfile "cable-summary.ini")) (setq l (cons hit l)))
  ;; 0b) the official Autoloader bundle (hand-copied folder): \%APPDATA%\Autodesk\ApplicationPlugins
  (if (setq hit (cblsum:bundle-contents))
    (setq l (cons (strcat hit "cable-summary.ini") l)))
  (setq l (cons (strcat (getenv "USERPROFILE") "\\Desktop\\cad-plugin\\cable-summary.ini") l))
  (setq l (cons (strcat (getenv "USERPROFILE") "\\Desktop\\cable-summary.ini") l))
  l)

(defun cblsum:append-unique (lst item)
  (if (or (null item) (= item "") (member item lst)) lst (append lst (list item))))

(defun cblsum:folder-of (path)
  (if (and path (> (strlen path) 0)) (vl-filename-directory path) nil))

(defun cblsum:index-of (s ch / i n found)
  (setq i 1 n (strlen s) found nil)
  (while (and (<= i n) (null found))
    (if (= (substr s i 1) ch) (setq found i) (setq i (1+ i))))
  found)

(defun cblsum:split-semis (s / out pos rest)
  (setq out (list) rest s)
  (while (setq pos (cblsum:index-of rest ";"))
    (setq out (append out (list (substr rest 1 (1- pos))))
          rest (substr rest (1+ pos))))
  (if (> (strlen rest) 0) (setq out (append out (list rest))))
  out)

(defun cblsum:search-roots (/ l)
  ;; Only the AutoCAD support file search path: (findfile ...) searches it and returns
  ;; a full absolute path, which is exactly what this plugin needs. No drive scanning.
  (setq l (list))
  (if cblsum-home (setq l (cblsum:append-unique l (cblsum:folder-of cblsum-home))))
  l)

(defun cblsum:find-engine (/ roots hit f)
  (setq hit nil)
  ;; (findfile "cable-summary.exe") covers the support-path case (strategy A)
  (setq hit (findfile "cable-summary.exe"))
  ;; next to the config file that was found (bundle layout: exe sits beside the ini)
  (if (and (null hit) cblsum-config)
    (progn
      (setq f (strcat (cblsum:dir-of cblsum-config) "cable-summary.exe"))
      (if (findfile f) (setq hit f))))
  (if (null hit)
    (foreach r (cblsum:search-roots)
      (if (null hit)
        (progn
          (setq f (strcat r "\\cad-plugin\\cable-summary.exe"))
          (if (findfile f) (setq hit f))))))
  hit)

(defun cblsum:load-config (/ cands hit tried)
  ;; Search order: plugin folder (real load path) -> drawing folder -> support path
  ;; -> common spots. Each candidate is reported when nothing is found, so the log
  ;; itself shows where the plugin looked.
  (setq cands (cblsum:candidates))
  (setq cblsum-config nil tried "")
  (while cands
    (setq hit (car cands) cands (cdr cands))
    (if (and hit (> (strlen hit) 0))
      (progn
        (setq tried (strcat tried "\n    " hit))
        (if (and (null cblsum-config) (findfile hit))
          (setq cblsum-config hit)))))
  (if cblsum-config
    (princ (strcat "\n[cable-sum-schedule] config: " cblsum-config))
    (progn
      ;; Nothing configured at all. If this file came from the official bundle, write a
      ;; minimal config next to it - then dropping the bundle folder into
      ;; ApplicationPlugins is all a new user has to do (no install step).
      (if (cblsum:ensure-config)
        (princ (strcat "\n[cable-sum-schedule] config: " cblsum-config))
        (princ (strcat "\n[cable-sum-schedule] cable-summary.ini NOT FOUND. Looked in:"
                       tried)))))
  cblsum-config)

(defun cblsum:ini-get (key default / fh line val)
  (if cblsum-config
    (progn
      (setq fh (open cblsum-config "r") val default)
      (if fh
        (progn
          (while (setq line (read-line fh))
            (setq line (cblsum:trim line))
            (if (and (> (strlen line) 0)
                     (/= (substr line 1 1) ";")
                     (= 0 (vl-string-search (strcat key "=") line)))
              (setq val (cblsum:trim (substr line (+ 2 (strlen key)))))))
          (close fh)))
      (if (= val "") default val))
    default))

(defun cblsum:collect (ss / i ent ed typ h lay pt ht txt rows)
  (setq i 0 rows '())
  (while (< i (sslength ss))
    (setq ent (ssname ss i)
          ed  (entget ent)
          typ (cblsum:cdr 0 ed)
          h   (cblsum:cdr 5 ed)
          lay (cblsum:cdr 8 ed))
    (if (member typ '("TEXT" "ATTRIB" "MTEXT"))
      (progn
        (setq txt (cblsum:cdr 1 ed)
              pt  (cblsum:cdr 10 ed)
              ht  (cblsum:num (cblsum:cdr 40 ed) 0.0))
        (if (and pt txt (/= txt ""))
          (setq rows (cons (list h lay (car pt) (cadr pt) ht txt) rows)))))
    (setq i (1+ i)))
  (reverse rows))

(defun cblsum:write-tsv (rows path / fh ok)
  (setq fh (open path "w") ok T)
  (if (null fh)
    (setq ok nil)
    (progn
      (write-line "handle\tlayer\tx\ty\theight\ttext" fh)
      (foreach r rows
        (write-line
          (strcat (nth 0 r) "\t" (nth 1 r) "\t"
                  (rtos (nth 2 r) 2 8) "\t" (rtos (nth 3 r) 2 8) "\t"
                  (rtos (nth 4 r) 2 4) "\t"
                  (vl-string-translate "\t\r\n" "   " (nth 5 r)))
          fh))
      (close fh)))
  ok)

(defun cblsum:open-file (path / quoted)
  "Open a file with its default application, trying more than one route.
   startapp alone is not reliable for .xlsx on every AutoCAD build."
  (if (or (null path) (null (findfile path)))
    nil
    (progn
      (setq quoted (strcat "\"" path "\""))
      (startapp (strcat "explorer " quoted))
      T)))

(defun cblsum:wait-ms (ms / t0)
  "Busy wait. The plugin runs on the document thread, so nothing else can run
   anyway; DELAY is not available on the command line."
  (setq t0 (getvar "DATE"))
  (while (< (* 86400000.0 (- (getvar "DATE") t0)) ms)))

(defun cblsum:run (/ ss rows tsv runner proj extra outFh line fh
                     savePath msg tries engine outfile outarg stamp autoop)
  (princ (strcat "\n[cable-sum-schedule] Cable summary (offline)  v" cblsum-version))
  (cblsum:load-config)
  (setq runner (cblsum:ini-get "runner" "")
        proj   (cblsum:ini-get "project" "")
        extra  (cblsum:ini-get "extra_args" "")
        ;; menu edition settings; every one of them defaults to the behaviour of
        ;; the offline edition, so an ini without these keys changes nothing
        outfile (cblsum:ini-get "output_file" "")
        stamp  (cblsum:ini-get "timestamp" "")
        autoop (cblsum:ini-get "auto_open" "1"))
  ;; Result location from the settings dialog: ONE value, a full path. A .xlsx
  ;; path is the file itself, anything else is a folder. Trailing backslashes are
  ;; trimmed: a quote right after one would be swallowed by the launcher's
  ;; command-line parsing.
  (setq outarg "")
  (if (/= outfile "")
    (if (= (strcase (vl-filename-extension outfile)) ".XLSX")
      (setq outarg (strcat " --output \"" outfile "\""))
      (setq outarg (strcat " --output-dir \"" (vl-string-right-trim "\\" outfile) "\""))))
  ;; Zero-config: when nothing is configured, look for the bundled engine ourselves.
  ;; AutoLISP cannot tell a loaded file its own path, so we scan likely folders instead
  ;; of asking the user to run a setup script.
  (if (or (= runner "") (null (findfile runner)))
    (progn
      (princ "\n[cable-sum-schedule] locating the engine (first run only)...")
      (setq engine (cblsum:find-engine))
      (if engine
        (progn
          (setq runner (strcat (vl-filename-directory engine) "\\run.bat"))
          (if (null (findfile runner))
            (setq runner engine))
          (princ (strcat "\n[cable-sum-schedule] found: " runner)))
        (princ "\n[cable-sum-schedule] engine not found in the usual places."))))
  (cond
    ((= runner "")
     (princ "\n[cable-sum-schedule] Cannot find cable-summary.exe. Pick one of these two:")
     (princ "\n  A) add the cad-plugin folder to AutoCAD's support search path (no setup needed):")
     (princ "\n     OPTIONS - Files - Support File Search Path - Add - pick the cad-plugin folder")
     (princ "\n  B) or just double-click install.bat once in the cad-plugin folder;")
     (princ "\n     it writes the absolute paths into the config, so the folder can live anywhere."))
    ((null (findfile runner))
     (princ (strcat "\n[cable-sum-schedule] launcher not found: " runner))
     (princ "\nPlease re-extract the package, or run install.bat once."))
    (T
     (setq ss (ssget "_I"))
     (cond
       ((null ss)
        (princ "\n[cable-sum-schedule] Nothing selected.")
        (princ "\nSelect the cable table(s) in the drawing first (including headers), then run CABLE_SUM."))
       (T
        (setq rows (cblsum:collect ss))
        (princ (strcat "\n[cable-sum-schedule] selected " (itoa (sslength ss)) " object(s), "
                       "collected " (itoa (length rows)) " text entity(ies)."))
        (if (< (length rows) 20)
          (princ "\n[cable-sum-schedule] Note: very few text entities - you may have missed the table."))
        (setq tsv (vl-filename-mktemp "cblsum" nil ".tsv"))
        (cond
          ((null (cblsum:write-tsv rows tsv))
           (princ "\n[cable-sum-schedule] Cannot write temp file. Aborted."))
          (T
           (setq outFh (strcat (vl-filename-mktemp "cblsum" nil ".out")))
           (princ "\n[cable-sum-schedule] Running local summary, waiting up to 120s...")
           (startapp (strcat "\"" runner "\""
                             " --input \"" tsv "\""
                             (if (/= proj "") (strcat " --project \"" proj "\"") "")
                             outarg
                             (if (= stamp "1") " --timestamp" "")
                             (if (/= extra "") (strcat " " extra) "")
                             " --response \"" outFh "\""))
           (setq savePath nil msg nil tries 0)
           (while (and (null savePath) (null msg) (< tries 600))
             (if (findfile outFh)
               (progn
                 (setq fh (open outFh "r"))
                 (while (setq line (read-line fh))
                   (cond ((= 0 (vl-string-search "SAVE_PATH=" line))
                          (setq savePath (cblsum:trim (substr line 11))))
                         ((= 0 (vl-string-search "MESSAGE=" line))
                          (setq msg (cblsum:unescape (cblsum:trim (substr line 9)))))
                         ((= 0 (vl-string-search "ERROR=" line))
                          (setq msg (strcat "ERROR: " (cblsum:trim (substr line 7)))))))
                 (close fh))
               (cblsum:wait-ms 200))
             (setq tries (1+ tries)))
           (if (findfile tsv)   (vl-file-delete tsv))
           (if (findfile outFh) (vl-file-delete outFh))
           (cond
             ((and savePath (findfile savePath))
              (princ "\n[cable-sum-schedule] Done.")
              (if msg (princ (strcat "\n" msg)))
              (princ (strcat "\n[cable-sum-schedule] Result file: " savePath))
              (cond
                ((= autoop "0")
                 (princ "\n[cable-sum-schedule] auto-open is off - open it when you need it."))
                ((cblsum:open-file savePath)
                 (princ "\n[cable-sum-schedule] Opened the result file with the default application."))
                (T
                 (princ (strcat "\n[cable-sum-schedule] Could not open it automatically - please open: "
                                savePath)))))
             (savePath
              (princ (strcat "\n[cable-sum-schedule] launcher reported path " savePath " but the file does not exist.")))
             (T
              (princ "\n[cable-sum-schedule] No response from the launcher (timeout or failed to start).")
              (if msg (princ (strcat "\n" msg)))
              (princ "\nChecks: 1) run the self-test .bat first;")
              (princ " 2) make sure runner points to the launcher .bat;")
              (princ " 3) make sure cable-summary.exe exists in this folder.")))))))))
  (princ))

(defun c:CABLE_SUM () (cblsum:run))
(defun c:CBLSUM () (cblsum:run))

(princ (strcat "\n[cable-sum-schedule] plugin loaded v" cblsum-version))
(if (and cblsum-ini (> (strlen cblsum-ini) 0))
  (princ (strcat "\n[cable-sum-schedule] config: " cblsum-ini))
  (if (cblsum:ensure-config)
    (princ (strcat "\n[cable-sum-schedule] config: " cblsum-ini))
    (princ "\n[cable-sum-schedule] config: not baked in - run install.bat to fix that")))
(princ "\n[cable-sum-schedule] offline: select the cable table, then run CABLE_SUM (alias CBLSUM)")
(princ)
