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
          (princ "\n[\265\347\300\302\273\343\327\334] \312\327\264\316\324\313\320\320\243\272\322\321\324\332\262\345\274\376\304\277\302\274\300\357\311\372\263\311 cable-summary.ini\241\243")
          (if (cblsum:trusted-path-add dir)
            (princ "\n[\265\347\300\302\273\343\327\334] \262\345\274\376\304\277\302\274\322\321\274\323\310\353\312\334\320\305\310\316\316\273\326\303\243\250\322\324\272\363\306\364\266\257\262\273\324\331\321\257\316\312\243\251\241\243"))
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
    (princ (strcat "\n[\265\347\300\302\273\343\327\334] \305\344\326\303\316\304\274\376: " cblsum-config))
    (progn
      ;; Nothing configured at all. If this file came from the official bundle, write a
      ;; minimal config next to it - then dropping the bundle folder into
      ;; ApplicationPlugins is all a new user has to do (no install step).
      (if (cblsum:ensure-config)
        (princ (strcat "\n[\265\347\300\302\273\343\327\334] \305\344\326\303\316\304\274\376: " cblsum-config))
        (princ (strcat "\n[\265\347\300\302\273\343\327\334] \325\322\262\273\265\275 cable-summary.ini\243\254\322\321\262\351\325\322\322\324\317\302\316\273\326\303:"
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
  (princ (strcat "\n[\265\347\300\302\273\343\327\334] \300\353\317\337\260\346  v" cblsum-version))
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
      (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\266\250\316\273\322\375\307\346\243\250\275\366\312\327\264\316\320\350\322\252\243\251...")
      (setq engine (cblsum:find-engine))
      (if engine
        (progn
          (setq runner (strcat (vl-filename-directory engine) "\\run.bat"))
          (if (null (findfile runner))
            (setq runner engine))
          (princ (strcat "\n[cable-sum-schedule] found: " runner)))
        (princ "\n[\265\347\300\302\273\343\327\334] \324\332\326\247\263\326\302\267\276\266\272\315 C:\134cable-summary \266\274\303\273\323\320\325\322\265\275\322\375\307\346\241\243"))))
  (cond
    ((= runner "")
     (princ "\n[\265\347\300\302\273\343\327\334] \325\322\262\273\265\275 cable-summary.exe\243\254\301\275\326\326\275\342\276\366\260\354\267\250\243\272")
     (princ "\n  \274\327\243\251\260\321 cad-plugin \304\277\302\274\274\323\310\353 AutoCAD \265\304\326\247\263\326\316\304\274\376\313\321\313\367\302\267\276\266\243\272")
     (princ "\n     \321\241\317\356 \241\372 \316\304\274\376 \241\372 \326\247\263\326\316\304\274\376\313\321\313\367\302\267\276\266 \241\372 \314\355\274\323 \241\372 \321\241\326\320 cad-plugin \304\277\302\274")
     (princ "\n     \326\273\320\350\324\332\261\276\304\277\302\274\313\253\273\367\322\273\264\316 install.bat\243\273")
     (princ "\n      \313\374\273\341\260\321\276\370\266\324\302\267\276\266\320\264\275\370\305\344\326\303\243\254\322\362\264\313\262\345\274\376\304\277\302\274\277\311\322\324\267\305\324\332\310\316\322\342\316\273\326\303\241\243"))
    ((null (findfile runner))
     (princ (strcat "\n[\265\347\300\302\273\343\327\334] \325\322\262\273\265\275\306\364\266\257\306\367: " runner))
     (princ "\n\307\353\326\330\320\302\275\342\321\271\260\262\327\260\260\374\243\254\273\362\324\313\320\320\322\273\264\316 install.bat\241\243"))
    (T
     (setq ss (ssget "_I"))
     (cond
       ((null ss)
        (princ "\n[\265\347\300\302\273\343\327\334] \265\261\307\260\303\273\323\320\321\241\326\320\266\324\317\363\241\243")
        (princ "\n\307\353\317\310\324\332\315\274\326\275\326\320\277\362\321\241\265\347\300\302\261\355\243\250\301\254\315\254\261\355\315\267\243\251\243\254\324\331\312\344\310\353 CABLE_SUM\241\243"))
       (T
        (setq rows (cblsum:collect ss))
        (princ (strcat "\n[\265\347\300\302\273\343\327\334] \321\241\326\320 " (itoa (sslength ss)) " \270\366\266\324\317\363\243\254"
                       "\266\301\310\241\265\275 " (itoa (length rows)) " \270\366\316\304\327\326\266\324\317\363\241\243"))
        (if (< (length rows) 20)
          (princ "\n[\265\347\300\302\273\343\327\334] \314\341\312\276\243\272\316\304\327\326\266\324\317\363\272\334\311\331\243\254\277\311\304\334\302\251\321\241\301\313\261\355\270\361\304\332\310\335\241\243"))
        (setq tsv (vl-filename-mktemp "cblsum" nil ".tsv"))
        (cond
          ((null (cblsum:write-tsv rows tsv))
           (princ "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\320\264\310\353\301\331\312\261\316\304\274\376\243\254\322\321\326\320\326\271\241\243"))
          (T
           (setq outFh (strcat (vl-filename-mktemp "cblsum" nil ".out")))
           (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\261\276\265\330\273\343\327\334\243\254\327\356\263\244\265\310\264\375 120 \303\353...")
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
                          (setq msg (strcat "\264\355\316\363\243\272" (cblsum:trim (substr line 7)))))))
                 (close fh))
               (cblsum:wait-ms 200))
             (setq tries (1+ tries)))
           (if (findfile tsv)   (vl-file-delete tsv))
           (if (findfile outFh) (vl-file-delete outFh))
           (cond
             ((and savePath (findfile savePath))
              (princ "\n[\265\347\300\302\273\343\327\334] \315\352\263\311\241\243")
              (if msg (princ (strcat "\n" msg)))
              (princ (strcat "\n[\265\347\300\302\273\343\327\334] \275\341\271\373\316\304\274\376: " savePath))
              (cond
                ((= autoop "0")
                 (princ "\n[\265\347\300\302\273\343\327\334] \322\321\271\330\261\325\327\324\266\257\264\362\277\252\243\254\320\350\322\252\312\261\307\353\327\324\320\320\264\362\277\252\275\341\271\373\316\304\274\376\241\243"))
                ((cblsum:open-file savePath)
                 (princ "\n[\265\347\300\302\273\343\327\334] \322\321\323\303\304\254\310\317\263\314\320\362\264\362\277\252\275\341\271\373\316\304\274\376\241\243"))
                (T
                 (princ (strcat "\n[cable-sum-schedule] Could not open it automatically - please open: "
                                savePath)))))
             (savePath
              (princ (strcat "\n[\265\347\300\302\273\343\327\334] \306\364\266\257\306\367\261\250\270\346\302\267\276\266 " savePath "\243\254\265\253\316\304\274\376\262\273\264\346\324\332\241\243")))
             (T
              (princ "\n[\265\347\300\302\273\343\327\334] \316\264\312\325\265\275\306\364\266\257\306\367\317\354\323\246\243\250\263\254\312\261\273\362\316\264\304\334\306\364\266\257\243\251\241\243")
              (if msg (princ (strcat "\n" msg)))
              (princ "\n\305\305\262\351\243\2721) \317\310\305\334\322\273\264\316 check.bat\243\273")
              (princ " 2) \310\267\310\317 runner \326\270\317\362 run.bat\243\273")
              (princ " 3) \310\267\310\317\261\276\304\277\302\274\323\320 cable-summary.exe\241\243")))))))))
  (princ))

(defun c:CABLE_SUM () (cblsum:run))
(defun c:CBLSUM () (cblsum:run))

(princ (strcat "\n[\265\347\300\302\273\343\327\334] \262\345\274\376\322\321\274\323\324\330 v" cblsum-version))
(if (and cblsum-ini (> (strlen cblsum-ini) 0))
  (princ (strcat "\n[\265\347\300\302\273\343\327\334] \305\344\326\303\316\304\274\376: " cblsum-ini))
  (if (cblsum:ensure-config)
    (princ (strcat "\n[\265\347\300\302\273\343\327\334] \305\344\326\303\316\304\274\376: " cblsum-ini))
    (princ "\n[\265\347\300\302\273\343\327\334] \311\320\316\264\305\344\326\303\243\272\307\353\317\310\313\253\273\367 install.bat")))
(princ "\n[\265\347\300\302\273\343\327\334] \323\303\267\250\243\272\317\310\277\362\321\241\265\347\300\302\261\355\243\254\324\331\312\344\310\353 CABLE_SUM\243\250\266\314\303\374\301\356 CBLSUM\243\251")
(princ)


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
(setq cblsum-default-name "\265\347\300\302\273\343\327\334\261\355.xlsx")

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
  (setq picked (getfiled "\321\241\324\361\275\341\271\373\261\243\264\346\265\304\316\273\326\303\323\353\316\304\274\376\303\373" init "xlsx" 1))
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
      (princ "\n[[\265\347\300\302\273\343\327\334] \311\350\326\303\266\324\273\260\277\362\320\350\322\252\316\304\274\376: cable-summary-settings.dcl")
      nil)
    (progn
      (setq ok (load_dialog dcl))
      (if (< ok 0)
        (progn
          (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\274\323\324\330\266\324\273\260\277\362: " dcl))
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
                (princ "\n[\265\347\300\302\273\343\327\334] \266\324\273\260\277\362\261\273\306\344\313\373\303\374\301\356\326\320\266\317\301\313\241\243"))
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
      (princ "\n[\265\347\300\302\273\343\327\334] \311\350\326\303\322\321\261\243\264\346"))
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
      (princ (strcat "\n[\265\347\300\302\273\343\327\334] \275\341\271\373\304\277\302\274: " dir))
      (startapp (strcat "explorer \"" dir "\"")))
    (princ "\n[\265\347\300\302\273\343\327\334] \273\271\303\273\323\320\275\341\271\373\304\277\302\274\243\254\324\335\316\336\277\311\264\362\277\252\265\304\316\273\326\303\241\243"))
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
     (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\324\313\320\320\327\324\274\354\241\252\241\252\307\353\277\264\270\325\265\257\263\366\265\304\264\260\277\332\300\357\265\304\275\341\271\373\241\243")
     (startapp (strcat "\"" bat "\"")))
    ((and exe (findfile exe))
     (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\324\313\320\320\327\324\274\354\241\252\241\252\307\353\277\264\270\325\265\257\263\366\265\304\264\260\277\332\300\357\265\304\275\341\271\373\241\243")
     (startapp (strcat "cmd.exe /k \"" exe "\" --self-test")))
    (T
     (princ "\n[\265\347\300\302\273\343\327\334] \325\322\262\273\265\275 check.bat\243\254\307\353\324\332 cad-plugin \304\277\302\274\300\357\312\326\266\257\324\313\320\320\313\374\241\243")))
  (princ))

(defun c:CABLE_SUM_ABOUT (/ r)
  (princ (strcat "\n[\265\347\300\302\273\343\327\334] \260\346\261\276 " cblsum-version " (menu edition)"))
  (princ (strcat "\n\305\344\326\303\316\304\274\376: " (if (cblsum:setting-file) (cblsum:setting-file) "(not found)")))
  (setq r (cblsum:ini-get "runner" ""))
  (princ (strcat "\n\322\375\307\346      : " (if (= r "") "(not configured)" r)))
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
(setq cblsum-menu-name "\265\347\300\302\315\263\274\306")

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
      (princ "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\266\301\310\241 AutoCAD \265\304\262\313\265\245\327\351\241\243")
      nil)
    (progn
      (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs cblsum-menu-group))))
      (if grp
        (princ (strcat "\n[\265\347\300\302\273\343\327\334] \321\330\323\303\322\321\323\320\265\304\262\313\265\245\327\351: " cblsum-menu-group))
        (progn
          (setq res (cblsum:com 'vla-Add (list mgs cblsum-menu-group)))
          (setq grp (cblsum:com-val res))
          (if grp
            (princ (strcat "\n[\265\347\300\302\273\343\327\334] \322\321\264\264\275\250\262\313\265\245\327\351: " cblsum-menu-group))
            (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\264\264\275\250\262\313\265\245\327\351 "
                           cblsum-menu-group ": " (cblsum:com-err res))))))
      (if (null grp)
        (progn
          (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs "ACAD"))))
          (if (null grp)
            (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs 0)))))
          (if grp
            (progn
              (princ "\n[\265\347\300\302\273\343\327\334] \270\304\323\303\273\371\261\276\262\313\265\245\327\351\241\243")
              (princ "\n[\265\347\300\302\273\343\327\334] \270\303\262\313\265\245\275\366\324\332\261\276\264\316 AutoCAD \273\341\273\260\326\320\323\320\320\247\241\243"))
            (princ "\n[\265\347\300\302\273\343\327\334] \303\273\323\320\277\311\323\303\265\304\262\313\265\245\327\351\243\254\316\336\267\250\264\264\275\250\262\313\265\245\241\243"))))
      grp)))

(defun cblsum:menu-append (menu label macro / res)
  "Append one command item at the end of the popup menu."
  (setq res (cblsum:com 'vla-AddMenuItem
                        (list menu (cblsum:menu-end-index menu) label macro)))
  (if (vl-catch-all-error-p res)
    (progn
      (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\314\355\274\323\262\313\265\245\317\356 "
                     label ": " (cblsum:com-err res)))
      nil)
    (progn
      (princ (strcat "\n[\265\347\300\302\273\343\327\334] \322\321\314\355\274\323\262\313\265\245\317\356: " label))
      T)))

(defun cblsum:menu-append-sep (menu / res)
  "Append one separator at the end of the popup menu."
  (setq res (cblsum:com 'vla-AddSeparator (list menu (cblsum:menu-end-index menu))))
  (if (vl-catch-all-error-p res)
    (progn
      (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\314\355\274\323\267\326\270\364\317\337: " (cblsum:com-err res)))
      nil)
    (progn
      (princ "\n[\265\347\300\302\273\343\327\334] \322\321\314\355\274\323\267\326\270\364\317\337\241\243")
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
  (cblsum:menu-append menu "\315\263\274\306\321\241\326\320\265\347\300\302\261\355" (cblsum:macro "CABLE_SUM"))
  (cblsum:menu-append-sep menu)
  (cblsum:menu-append menu "\315\263\274\306\311\350\326\303\241\255" (cblsum:macro "CABLE_SUM_SETTINGS"))
  (cblsum:menu-append menu "\264\362\277\252\275\341\271\373\304\277\302\274" (cblsum:macro "CABLE_SUM_OPEN"))
  (cblsum:menu-append-sep menu)
  (cblsum:menu-append menu "\327\324\274\354" (cblsum:macro "CABLE_SUM_CHECK"))
  (cblsum:menu-append menu "\271\330\323\332" (cblsum:macro "CABLE_SUM_ABOUT"))
  (cblsum:menu-append menu "\320\266\324\330\262\313\265\245" (cblsum:macro "CABLE_SUM_MENU_REMOVE"))
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
      (princ "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\300\270\311\317\322\321\323\320\270\303\262\313\265\245\243\254\262\273\324\331\326\330\270\264\314\355\274\323\241\243")
      T)
    (progn
      (setq n (cblsum:com-val (cblsum:com 'vla-get-Count (list bar))))
      (if (null n) (setq n 0))
      (setq res (cblsum:com 'vla-InsertInMenuBar (list pop n)))
      (if (vl-catch-all-error-p res)
        (setq res (cblsum:com 'vla-InsertInMenuBar (list pop (1+ n)))))
      (if (vl-catch-all-error-p res)
        (progn
          (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\260\321\262\313\265\245\274\323\265\275\262\313\265\245\300\270: "
                         (cblsum:com-err res)))
          nil)
        (progn
          (princ "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\322\321\274\323\265\275\262\313\265\245\300\270\243\250\307\353\277\264\327\356\323\322\261\337\243\251\241\243")
          T)))))

(defun cblsum:menu-put-on-bar (app pop / bar)
  "Insert the popup menu into the menu bar of the active drawing."
  (setq bar (if app (cblsum:menu-bar-of app) nil))
  (if (null bar)
    (progn
      (princ "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\266\301\310\241\265\261\307\260\315\274\326\275\265\304\262\313\265\245\300\270\241\243")
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
     (princ "\n[\265\347\300\302\273\343\327\334] \262\345\274\376\304\277\302\274\317\302\325\322\262\273\265\275 cable-summary.cuix\241\243")
     nil)
    (T
     (princ (strcat "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\316\304\274\376: " cuix))
     (setq mgs (cblsum:com-val (cblsum:com 'vla-get-MenuGroups (list app))))
     (setq grp (cblsum:com-val (cblsum:com 'vla-Item (list mgs cblsum-menu-group))))
     (if grp
       (princ (strcat "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\327\351\322\321\276\255\274\323\324\330: " cblsum-menu-group))
       (progn
         ;; :vlax-false loads the file as a PARTIAL menu. Loading it as the base
         ;; menu would replace every menu of the running AutoCAD session.
         (setq res (cblsum:com 'vla-Load (list mgs cuix :vlax-false)))
         (setq grp (cblsum:com-val res))
         (if grp
           (princ (strcat "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\327\351\322\321\274\323\324\330: " cblsum-menu-group))
           (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\274\323\324\330\262\313\265\245\316\304\274\376: "
                          (cblsum:com-err res))))))
     (setq pop (if grp (cblsum:menu-popup-in-group app cblsum-menu-group) nil))
     (cond
       ((null pop)
        (princ (strcat "\n[\265\347\300\302\273\343\327\334] \274\323\324\330\265\304\262\313\265\245\316\304\274\376\300\357\303\273\323\320\325\342\270\366\262\313\265\245: "
                       cblsum-menu-name))
        nil)
       (T
        (cblsum:menu-put-on-bar app pop))))))

(defun c:CABLE_SUM_MENU (/ app grp menus pop res ok)
  (cblsum:load-config)
  (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\323\303 COM \264\264\275\250\262\313\265\245\243\254\262\273\320\350\322\252\262\313\265\245\316\304\274\376...")
  (vl-load-com)
  (setq app (vlax-get-acad-object))
  (if (null app)
    (princ "\n[\265\347\300\302\273\343\327\334] \265\261\307\260 AutoCAD \262\273\326\247\263\326 COM \275\323\277\332\241\243")
    (progn
      (setq ok nil)
      (setq grp (cblsum:menu-group-of app))
      (if grp
        (progn
          (setq menus (cblsum:com-val (cblsum:com 'vla-get-Menus (list grp))))
          (setq pop (cblsum:menu-popup-find menus))
          (if pop
            (progn
              (princ (strcat "\n[\265\347\300\302\273\343\327\334] \321\330\323\303\322\321\323\320\265\304\265\257\263\366\262\313\265\245: " cblsum-menu-name))
              ;; an empty popup is a leftover from an interrupted run: fill it
              (setq res (cblsum:com 'vla-get-Count (list pop)))
              (if (or (vl-catch-all-error-p res) (= 0 res))
                (cblsum:menu-fill pop)))
            (progn
              (setq res (cblsum:com 'vla-Add (list menus cblsum-menu-name)))
              (setq pop (cblsum:com-val res))
              (if pop
                (progn
                  (princ (strcat "\n[\265\347\300\302\273\343\327\334] \322\321\264\264\275\250\265\257\263\366\262\313\265\245: " cblsum-menu-name))
                  (cblsum:menu-fill pop))
                (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\264\264\275\250\265\257\263\366\262\313\265\245: "
                               (cblsum:com-err res))))))
          (if pop
            (setq ok (cblsum:menu-put-on-bar app pop)))))
      ;; fallback route: only when the COM route produced no menu on the bar
      (if (null ok)
        (progn
          (princ "\n[\265\347\300\302\273\343\327\334] COM \267\275\312\275\316\264\315\352\263\311\243\254\270\304\323\303\262\313\265\245\316\304\274\376\326\330\312\324\241\243")
          (setq ok (cblsum:menu-from-cuix app))))
      (if (null ok)
        (princ "\n[\265\347\300\302\273\343\327\334] \316\264\304\334\264\264\275\250\262\313\265\245\241\243")
        (if (vl-catch-all-error-p (vl-catch-all-apply 'setvar (list "MENUBAR" 1)))
          (princ "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\264\362\277\252\262\313\265\245\300\270\317\324\312\276\241\243")
          (princ "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\300\270\317\324\312\276\322\321\264\362\277\252\243\250MENUBAR=1\243\251\241\243")))))
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
    (princ "\n[\265\347\300\302\273\343\327\334] \265\261\307\260 AutoCAD \262\273\326\247\263\326 COM \275\323\277\332\241\243")
    (progn
      ;; 1) the real job: take the menu off the menu bar. The menu lives either in
      ;;    its own CABLESUM group or in the base group (ACAD), so look in both.
      (setq inbase nil)
      (setq pop (cblsum:menu-popup-in-group app cblsum-menu-group))
      (if pop
        (princ "\n[\265\347\300\302\273\343\327\334] \324\332 CABLESUM \262\313\265\245\327\351\300\357\325\322\265\275\301\313\265\257\263\366\262\313\265\245\241\243")
        (progn
          (setq pop (cblsum:menu-popup-in-group app "ACAD"))
          (if pop
            (progn
              (setq inbase T)
              (princ "\n[\265\347\300\302\273\343\327\334] \324\332\273\371\261\276\262\313\265\245\327\351\243\250ACAD\243\251\300\357\325\322\265\275\301\313\265\257\263\366\262\313\265\245\241\243")))))
      (cond
        ((null pop)
         (princ "\n[\265\347\300\302\273\343\327\334] \265\261\307\260\303\273\323\320\274\323\324\330\265\347\300\302\315\263\274\306\262\313\265\245\241\243"))
        ((null (setq bar (cblsum:menu-bar-of app)))
         (princ "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\266\301\310\241\265\261\307\260\315\274\326\275\265\304\262\313\265\245\300\270\241\243"))
        ((null (cblsum:menu-bar-holds-p bar))
         (princ "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\262\273\324\332\262\313\265\245\300\270\311\317\243\254\316\336\320\350\322\306\263\375\241\243"))
        (T
         (setq res (cblsum:com 'vla-RemoveFromMenuBar (list pop)))
         (if (vl-catch-all-error-p res)
           (princ (strcat "\n[\265\347\300\302\273\343\327\334] \316\336\267\250\260\321\262\313\265\245\264\323\262\313\265\245\300\270\322\306\263\375: "
                          (cblsum:com-err res)))
           (princ "\n[\265\347\300\302\273\343\327\334] \322\321\260\321\262\313\265\245\264\323\262\313\265\245\300\270\322\306\263\375\241\243"))))
      ;; 2) unload the group, but only when it exists (see the note above)
      (setq grp (cblsum:menu-group-find app cblsum-menu-group))
      (if grp
        (progn
          (princ "\n[\265\347\300\302\273\343\327\334] \325\375\324\332\320\266\324\330\262\313\265\245\327\351 CABLESUM...")
          (setq res (vl-catch-all-apply 'command (list "_.MENUUNLOAD" cblsum-menu-group)))
          (if (vl-catch-all-error-p res)
            (princ (strcat "\n[\265\347\300\302\273\343\327\334] MENUUNLOAD \312\247\260\334: " (cblsum:com-err res)))
            (princ "\n[\265\347\300\302\273\343\327\334] \262\313\265\245\327\351\322\321\320\266\324\330\241\243")))
        (progn
          (princ "\n[\265\347\300\302\273\343\327\334] CABLESUM \262\313\265\245\327\351\316\264\274\323\324\330\243\254\316\336\320\350\320\266\324\330\241\243")
          (if inbase
            (princ "\n[\265\347\300\302\273\343\327\334] \273\371\261\276\262\313\265\245\327\351\262\273\304\334\320\266\324\330\241\252\241\252\262\313\265\245\301\364\324\332\306\344\326\320\243\254\317\302\264\316\277\311\326\261\275\323\270\264\323\303\241\243"))))
      (princ "\n[\265\347\300\302\273\343\327\334] \322\252\263\271\265\327\322\306\263\375\262\345\274\376\243\254\307\353\324\313\320\320\262\345\274\376\304\277\302\274\300\357\265\304 uninstall.bat\241\243")))
  (princ))

;; ---------- menu edition: build the menu as soon as this file is loaded ----------
;; AutoCAD loads this file at every start (official Autoloader: the bundle in
;; ApplicationPlugins declares it), and the load itself puts the menu on the menu
;; bar. Having the menu already is not an error - c:CABLE_SUM_MENU reuses it
;; instead of adding a second one - so APPLOADing the file by hand still works.
;; Wrapped in vl-catch-all-apply: a menu problem must never break the load.
(vl-catch-all-apply (function c:CABLE_SUM_MENU) nil)

