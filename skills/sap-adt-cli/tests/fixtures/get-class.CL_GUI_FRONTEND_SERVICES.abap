class CL_GUI_FRONTEND_SERVICES definition
  public
  inheriting from CL_GUI_OBJECT
  final
  create public .

public section.

  constants HKEY_CLASSES_ROOT type I value 0 ##NO_TEXT.
  constants HKEY_CURRENT_USER type I value 1 ##NO_TEXT.
  constants HKEY_LOCAL_MACHINE type I value 2 ##NO_TEXT.
  constants HKEY_USERS type I value 3 ##NO_TEXT.
  constants PLATFORM_UNKNOWN type I value -1 ##NO_TEXT.
  constants PLATFORM_WINDOWS95 type I value 1 ##NO_TEXT.
  constants PLATFORM_WINDOWS98 type I value 2 ##NO_TEXT.
  constants PLATFORM_NT351 type I value 3 ##NO_TEXT.
  constants PLATFORM_NT40 type I value 4 ##NO_TEXT.
  constants PLATFORM_NT50 type I value 5 ##NO_TEXT.
  constants PLATFORM_MAC type I value 6 ##NO_TEXT.
  constants PLATFORM_OS2 type I value 7 ##NO_TEXT.
  constants PLATFORM_LINUX type I value 8 ##NO_TEXT.
  constants PLATFORM_HPUX type I value 9 ##NO_TEXT.
  constants PLATFORM_TRU64 type I value 10 ##NO_TEXT.
  constants PLATFORM_AIX type I value 11 ##NO_TEXT.
  constants PLATFORM_SOLARIS type I value 12 ##NO_TEXT.
  constants PLATFORM_MACOSX type I value 13 ##NO_TEXT.
  constants ACTION_OK type I value 0 ##NO_TEXT.
  constants ACTION_CANCEL type I value 9 ##NO_TEXT.
  class-data FILETYPE_ALL type STRING read-only .
  class-data FILETYPE_TEXT type STRING read-only .
  class-data FILETYPE_XML type STRING read-only .
  class-data FILETYPE_HTML type STRING read-only .
  class-data FILETYPE_EXCEL type STRING read-only .
  class-data FILETYPE_RTF type STRING read-only .
  class-data FILETYPE_WORD type STRING read-only .
  class-data FILETYPE_POWERPOINT type STRING read-only .
  constants PLATFORM_WINDOWSXP type I value 14 ##NO_TEXT.
  constants ACTION_APPEND type I value 1 ##NO_TEXT.
  constants ACTION_REPLACE type I value 2 ##NO_TEXT.
  class-data GUIDELINE_CLASSIC type I value 1 ##NO_TEXT.
  class-data GUIDELINE_FIORI_2 type I value 2 ##NO_TEXT.

  class-methods GET_FEATURES_TAB
    returning
      value(FEATURES_TAB) type SFES_FEATURES_TAB_TYPE
    exceptions
      UNKNOWN_ERROR .
  class-methods CHECK_GUI_SUPPORT
    importing
      !COMPONENT type STRING optional
      !FEATURE_NAME type STRING optional
    returning
      value(RESULT) type ABAP_BOOL
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI
      UNKNOWN_ERROR .
  class-methods CHECK_OPEN_NEW_WINDOW
    returning
      value(RESULT) type ABAP_BOOL .
  class-methods CLASS_CONSTRUCTOR .
  class-methods CLIPBOARD_EXPORT
    importing
      !NO_AUTH_CHECK type CHAR01 default SPACE
    exporting
      !DATA type STANDARD TABLE
    changing
      !RC type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      NO_AUTHORITY .
  class-methods CLIPBOARD_IMPORT
    importing
      !USE_DATA_LINE_SIZE type ABAP_BOOL optional
    exporting
      !DATA type STANDARD TABLE
      !LENGTH type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  methods CONSTRUCTOR
    exceptions
      NOT_SUPPORTED_BY_GUI
      CNTL_ERROR .
  class-methods DIRECTORY_BROWSE
    importing
      value(WINDOW_TITLE) type STRING optional
      value(INITIAL_FOLDER) type STRING optional
    changing
      !SELECTED_FOLDER type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods DIRECTORY_CREATE
    importing
      value(DIRECTORY) type STRING
    changing
      !RC type I
    exceptions
      DIRECTORY_CREATE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      DIRECTORY_ACCESS_DENIED
      DIRECTORY_ALREADY_EXISTS
      PATH_NOT_FOUND
      UNKNOWN_ERROR
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods DIRECTORY_DELETE
    importing
      value(DIRECTORY) type STRING
    changing
      !RC type I
    exceptions
      DIRECTORY_DELETE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      PATH_NOT_FOUND
      DIRECTORY_ACCESS_DENIED
      UNKNOWN_ERROR
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods DIRECTORY_EXIST
    importing
      !DIRECTORY type STRING
    returning
      value(RESULT) type ABAP_BOOL
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods DIRECTORY_GET_CURRENT
    changing
      !CURRENT_DIRECTORY type STRING
    exceptions
      DIRECTORY_GET_CURRENT_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods DIRECTORY_LIST_FILES
    importing
      value(DIRECTORY) type STRING
      value(FILTER) type STRING default '*.*'
      value(FILES_ONLY) type ABAP_BOOL optional
      value(DIRECTORIES_ONLY) type ABAP_BOOL optional
    changing
      !FILE_TABLE type STANDARD TABLE
      !COUNT type I
    exceptions
      CNTL_ERROR
      DIRECTORY_LIST_FILES_FAILED
      WRONG_PARAMETER
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods DIRECTORY_LIST_FILES_EXT
    importing
      value(DIRECTORY) type STRING
      value(FILTER) type STRING default '*.*'
      value(FILES_ONLY) type ABAP_BOOL optional
      value(DIRECTORIES_ONLY) type ABAP_BOOL optional
    changing
      !FILE_TABLE type STANDARD TABLE
      !COUNT type I
    exceptions
      CNTL_ERROR
      DIRECTORY_LIST_FILES_FAILED
      WRONG_PARAMETER
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods DIRECTORY_SET_CURRENT
    importing
      value(CURRENT_DIRECTORY) type STRING
    changing
      !RC type I
    exceptions
      DIRECTORY_SET_CURRENT_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods DISABLEHISTORYFORFIELD
    importing
      value(FIELDNAME) type STRING
      value(BDISABLED) type ABAP_BOOL
    changing
      value(RC) type I
    exceptions
      FIELD_NOT_FOUND
      DISABLEHISTORYFORFIELD_FAILED
      CNTL_ERROR
      UNABLE_TO_DISABLE_FIELD
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods ENVIRONMENT_GET_VARIABLE
    importing
      value(VARIABLE) type STRING
    changing
      !VALUE type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods ENVIRONMENT_SET_VARIABLE
    importing
      value(VARIABLE) type STRING
      value(VALUE) type STRING
    changing
      !RC type I
    exceptions
      ENVIRONMENT_SET_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods EXECUTE
    importing
      value(DOCUMENT) type STRING optional
      value(APPLICATION) type STRING optional
      value(PARAMETER) type STRING optional
      value(DEFAULT_DIRECTORY) type STRING optional
      value(MAXIMIZED) type STRING optional
      value(MINIMIZED) type STRING optional
      value(SYNCHRONOUS) type STRING optional
      value(OPERATION) type STRING default 'OPEN'
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      BAD_PARAMETER
      FILE_NOT_FOUND
      PATH_NOT_FOUND
      FILE_EXTENSION_UNKNOWN
      ERROR_EXECUTE_FAILED
      SYNCHRONOUS_FAILED
      NOT_SUPPORTED_BY_GUI .
  class-methods FILE_COPY
    importing
      value(SOURCE) type STRING
      value(DESTINATION) type STRING
      value(OVERWRITE) type ABAP_BOOL default SPACE
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      WRONG_PARAMETER
      DISK_FULL
      ACCESS_DENIED
      FILE_NOT_FOUND
      DESTINATION_EXISTS
      UNKNOWN_ERROR
      PATH_NOT_FOUND
      DISK_WRITE_PROTECT
      DRIVE_NOT_READY
      NOT_SUPPORTED_BY_GUI .
  class-methods FILE_DELETE
    importing
      value(FILENAME) type STRING
    changing
      !RC type I
    exceptions
      FILE_DELETE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      FILE_NOT_FOUND
      ACCESS_DENIED
      UNKNOWN_ERROR
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods FILE_EXIST
    importing
      value(FILE) type STRING
    returning
      value(RESULT) type ABAP_BOOL
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods FILE_GET_ATTRIBUTES
    importing
      !FILENAME type STRING
    exporting
      !READONLY type ABAP_BOOL
      !NORMAL type ABAP_BOOL
      !HIDDEN type ABAP_BOOL
      !ARCHIVE type ABAP_BOOL
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER
      FILE_GET_ATTRIBUTES_FAILED .
  class-methods FILE_GET_SIZE
    importing
      value(FILE_NAME) type STRING
    exporting
      !FILE_SIZE type I
    exceptions
      FILE_GET_SIZE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      INVALID_DEFAULT_FILE_NAME .
  class-methods FILE_GET_SIZE_LONG
    importing
      value(FILE_NAME) type STRING
    exporting
      !FILE_SIZE type INT8
    exceptions
      FILE_GET_SIZE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      INVALID_DEFAULT_FILE_NAME .
  class-methods FILE_GET_VERSION
    importing
      value(FILENAME) type STRING
    changing
      !VERSION type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods FILE_OPEN_DIALOG
    importing
      value(WINDOW_TITLE) type STRING optional
      value(DEFAULT_EXTENSION) type STRING optional
      value(DEFAULT_FILENAME) type STRING optional
      value(FILE_FILTER) type STRING optional
      value(WITH_ENCODING) type ABAP_BOOL optional
      value(INITIAL_DIRECTORY) type STRING optional
      value(MULTISELECTION) type ABAP_BOOL optional
    changing
      !FILE_TABLE type FILETABLE
      !RC type I
      !USER_ACTION type I optional
      !FILE_ENCODING type ABAP_ENCODING optional
    exceptions
      FILE_OPEN_DIALOG_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods FILE_SAVE_DIALOG
    importing
      value(WINDOW_TITLE) type STRING optional
      value(DEFAULT_EXTENSION) type STRING optional
      value(DEFAULT_FILE_NAME) type STRING optional
      !WITH_ENCODING type ABAP_BOOL optional
      value(FILE_FILTER) type STRING optional
      value(INITIAL_DIRECTORY) type STRING optional
      !PROMPT_ON_OVERWRITE type ABAP_BOOL default 'X'
    changing
      !FILENAME type STRING
      !PATH type STRING
      !FULLPATH type STRING
      !USER_ACTION type I optional
      !FILE_ENCODING type ABAP_ENCODING optional
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      INVALID_DEFAULT_FILE_NAME .
  class-methods FILE_SET_ATTRIBUTES
    importing
      !FILENAME type STRING
      !READONLY type ABAP_BOOL optional
      !NORMAL type ABAP_BOOL optional
      !HIDDEN type ABAP_BOOL optional
      !ARCHIVE type ABAP_BOOL optional
    exporting
      !RC type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      WRONG_PARAMETER .
  class-methods GET_COMPUTER_NAME
    changing
      !COMPUTER_NAME type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_DESKTOP_DIRECTORY
    changing
      !DESKTOP_DIRECTORY type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_DRIVE_FREE_SPACE_MEGABYTE
    importing
      value(DRIVE) type STRING default 'C:\'
    changing
      !FREE_SPACE type STRING
    exceptions
      CNTL_ERROR
      GET_FREE_SPACE_FAILED
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_DRIVE_TYPE
    importing
      value(DRIVE) type STRING
    changing
      !DRIVE_TYPE type STRING
    exceptions
      CNTL_ERROR
      BAD_PARAMETER
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_FILE_SEPARATOR
    changing
      value(FILE_SEPARATOR) type C
    exceptions
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI
      CNTL_ERROR .
  class-methods GET_FREE_SPACE_FOR_DRIVE
    importing
      value(DRIVE) type STRING
    changing
      !FREE_SPACE type I
    exceptions
      CNTL_ERROR
      GET_FREE_SPACE_FAILED
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_FREE_SPACE_FOR_DRIVE_LONG
    importing
      value(DRIVE) type STRING
    changing
      !FREE_SPACE type INT8
    exceptions
      CNTL_ERROR
      GET_FREE_SPACE_FAILED
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_GUI_PROPERTIES
    changing
      !STREAM type STRING
    exceptions
      CNTL_ERROR
      GET_GUI_PROPERTIES_FAILED
      ERROR_NO_GUI
      WRONG_PARAMETER
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_GUI_VERSION
    changing
      !VERSION_TABLE type FILETABLE
      !RC type I
    exceptions
      GET_GUI_VERSION_FAILED
      CANT_WRITE_VERSION_TABLE
      GUI_NO_VERSION
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_IP_ADDRESS
    returning
      value(IP_ADDRESS) type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_LF_FOR_DESTINATION_GUI
    changing
      !LINEFEED type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_PLATFORM
    returning
      value(PLATFORM) type I
    exceptions
      ERROR_NO_GUI
      CNTL_ERROR
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_SAPGUI_DIRECTORY
    changing
      !SAPGUI_DIRECTORY type STRING
    exceptions
      CNTL_ERROR
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI .
  class-methods GET_SAPGUI_WORKDIR
    changing
      !SAPWORKDIR type STRING
    exceptions
      GET_SAPWORKDIR_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_SAPLOGON_ENCODING
    changing
      !FILE_ENCODING type ABAP_ENCODING
      !RC type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      CANNOT_INITIALIZE_GLOBALSTATE .
  class-methods GET_SYSTEM_DIRECTORY
    changing
      !SYSTEM_DIRECTORY type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_TEMP_DIRECTORY
    changing
      !TEMP_DIR type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_UPLOAD_DOWNLOAD_PATH
    changing
      value(UPLOAD_PATH) type STRING
      value(DOWNLOAD_PATH) type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI
      GUI_UPLOAD_DOWNLOAD_PATH
      UPLOAD_DOWNLOAD_PATH_FAILED .
  class-methods GET_USER_NAME
    changing
      !USER_NAME type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_WINDOWS_DIRECTORY
    changing
      !WINDOWS_DIRECTORY type STRING
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GUI_DOWNLOAD
    importing
      !BIN_FILESIZE type I optional
      !FILENAME type STRING
      !FILETYPE type CHAR10 default 'ASC'
      !APPEND type CHAR01 default SPACE
      !WRITE_FIELD_SEPARATOR type CHAR01 default SPACE
      !HEADER type XSTRING default '00'
      !TRUNC_TRAILING_BLANKS type CHAR01 default SPACE
      !WRITE_LF type CHAR01 default 'X'
      !COL_SELECT type CHAR01 default SPACE
      !COL_SELECT_MASK type CHAR255 default SPACE
      !DAT_MODE type CHAR01 default SPACE
      !CONFIRM_OVERWRITE type CHAR01 default SPACE
      !NO_AUTH_CHECK type CHAR01 default SPACE
      !CODEPAGE type ABAP_ENCODING default SPACE
      !IGNORE_CERR type ABAP_BOOL default ABAP_TRUE
      !REPLACEMENT type ABAP_REPL default '#'
      !WRITE_BOM type ABAP_BOOL default SPACE
      !TRUNC_TRAILING_BLANKS_EOL type CHAR01 default 'X'
      !WK1_N_FORMAT type C default SPACE
      !WK1_N_SIZE type C default SPACE
      !WK1_T_FORMAT type C default SPACE
      !WK1_T_SIZE type C default SPACE
      !SHOW_TRANSFER_STATUS type CHAR01 default 'X'
      !FIELDNAMES type STANDARD TABLE optional
      !WRITE_LF_AFTER_LAST_LINE type ABAP_BOOL default 'X'
      !VIRUS_SCAN_PROFILE type VSCAN_PROFILE default '/SCET/GUI_DOWNLOAD'
    exporting
      value(FILELENGTH) type I
    changing
      !DATA_TAB type STANDARD TABLE
    exceptions
      FILE_WRITE_ERROR
      NO_BATCH
      GUI_REFUSE_FILETRANSFER
      INVALID_TYPE
      NO_AUTHORITY
      UNKNOWN_ERROR
      HEADER_NOT_ALLOWED
      SEPARATOR_NOT_ALLOWED
      FILESIZE_NOT_ALLOWED
      HEADER_TOO_LONG
      DP_ERROR_CREATE
      DP_ERROR_SEND
      DP_ERROR_WRITE
      UNKNOWN_DP_ERROR
      ACCESS_DENIED
      DP_OUT_OF_MEMORY
      DISK_FULL
      DP_TIMEOUT
      FILE_NOT_FOUND
      DATAPROVIDER_EXCEPTION
      CONTROL_FLUSH_ERROR
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI .
  class-methods GUI_UPLOAD
    importing
      !FILENAME type STRING default SPACE
      !FILETYPE type CHAR10 default 'ASC'
      !HAS_FIELD_SEPARATOR type CHAR01 default SPACE
      !HEADER_LENGTH type I default 0
      !READ_BY_LINE type CHAR01 default 'X'
      !DAT_MODE type CHAR01 default SPACE
      !CODEPAGE type ABAP_ENCODING default SPACE
      !IGNORE_CERR type ABAP_BOOL default ABAP_TRUE
      !REPLACEMENT type ABAP_REPL default '#'
      !VIRUS_SCAN_PROFILE type VSCAN_PROFILE optional
    exporting
      value(FILELENGTH) type I
      value(HEADER) type XSTRING
    changing
      !DATA_TAB type STANDARD TABLE
      !ISSCANPERFORMED type CHAR01 default SPACE
    exceptions
      FILE_OPEN_ERROR
      FILE_READ_ERROR
      NO_BATCH
      GUI_REFUSE_FILETRANSFER
      INVALID_TYPE
      NO_AUTHORITY
      UNKNOWN_ERROR
      BAD_DATA_FORMAT
      HEADER_NOT_ALLOWED
      SEPARATOR_NOT_ALLOWED
      HEADER_TOO_LONG
      UNKNOWN_DP_ERROR
      ACCESS_DENIED
      DP_OUT_OF_MEMORY
      DISK_FULL
      DP_TIMEOUT
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI .
  class-methods IS_TERMINAL_SERVER
    returning
      value(RESULT) type ABAP_BOOL
    exceptions
      CNTL_ERROR
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI .
  class-methods REGISTRY_DELETE_KEY
    importing
      value(ROOT) type I
      value(KEY) type STRING
    exporting
      !RC type I
    exceptions
      CNTL_ERROR
      REGISTRY_DELETE_KEY_FAILED
      BAD_PARAMETER
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods REGISTRY_DELETE_VALUE
    importing
      value(ROOT) type I
      value(KEY) type STRING
      value(VALUE) type STRING
    exporting
      !RC type I
    exceptions
      CNTL_ERROR
      REGISTRY_DELETE_VALUE_FAILED
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods REGISTRY_GET_DWORD_VALUE
    importing
      value(ROOT) type I
      value(KEY) type STRING
      value(VALUE) type STRING optional
    exporting
      !REG_VALUE type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods REGISTRY_GET_VALUE
    importing
      value(ROOT) type I
      value(KEY) type STRING
      value(VALUE) type STRING optional
      !NO_FLUSH type C optional
    exporting
      !REG_VALUE type STRING
    exceptions
      GET_REGVALUE_FAILED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods REGISTRY_SET_DWORD_VALUE
    importing
      !ROOT type I
      !KEY type STRING
      !VALUE type STRING optional
      !DWORD_VALUE type I
    exporting
      !RC type I
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods REGISTRY_SET_VALUE
    importing
      value(ROOT) type I
      value(KEY) type STRING
      value(VALUE_NAME) type STRING optional
      value(VALUE) type STRING
    exporting
      !RC type I
    exceptions
      REGISTRY_ERROR
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods GET_SCREENSHOT
    exporting
      value(MIME_TYPE_STR) type STRING
      value(IMAGE) type XSTRING
    exceptions
      ACCESS_DENIED
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods RAISE_SCRIPTING_EVENT
    importing
      value(PARAMS) type STRING
    exceptions
      REGISTRY_ERROR
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods IS_SCRIPTING_ACTIVE
    returning
      value(RESULT) type I
    exceptions
      CNTL_ERROR
      NOT_SUPPORTED_BY_GUI
      ERROR_NO_GUI .
  class-methods SHOW_DOCUMENT
    importing
      !DOCUMENT_NAME type STRING
      !MIME_TYPE type STRING
      !DATA_LENGTH type I
      !KEEP_FILE type XFLAG optional
    exporting
      !TEMP_FILE_PATH type STRING
    changing
      !DOCUMENT_DATA type STANDARD TABLE
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      BAD_PARAMETER
      ERROR_WRITING_DATA
      ERROR_STARTING_VIEWER
      UNKNOWN_MIME_TYPE
      NOT_SUPPORTED_BY_GUI
      ACCESS_DENIED
      NO_AUTHORITY .
  class-methods TYPEAHEAD_EXPORT
    importing
      !DATA type STANDARD TABLE
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      NOT_SUPPORTED_BY_GUI .
  class-methods CHECK_UI_GUIDELINE
    importing
      !GUIDELINE type I
    returning
      value(RESULT) type ABAP_BOOL .
protected section.
*"* protected components of class CL_GUI_FRONTEND_SERVICES
*"* do not include other source files here!!!
private section.

*"* private components of class CL_GUI_FRONTEND_SERVICES
*"* do not include other source files here!!!
  class-data HANDLE type ref to CL_GUI_FRONTEND_SERVICES .
  class-data M_PLATFORM type I value 0. "#EC NOTEXT . " .
  class-data ICALL type I value 0. "#EC NOTEXT . " .
  class-data ERROR_CODE type I value 0. "#EC NOTEXT . " .
  class-data ERROR_NOT_SUPPORTED_BY_GUI type I value -1. "#EC NOTEXT . " .
  class-data ERROR_NO_GUI type I value -2. "#EC NOTEXT . " .
  class-data GUIFEATURE type STRING value 'GF'. "#EC NOTEXT . " .
  class-data FILE_SEPARATOR type C .
  class-data GUI_CRLF type STRING .
  type-pools ABAP .
  class-data SAPLOGON_ENCODING type ABAP_ENCODING .

  class-methods IS_VALID_HANDLE
    returning
      value(RCODE) type I .
  class-methods SHOW_DOCUMENT_FALLBACK
    importing
      !DOCUMENT_NAME type STRING
      !MIME_TYPE type STRING
      !DATA_LENGTH type I
    changing
      !DOCUMENT_DATA type STANDARD TABLE
    exceptions
      CNTL_ERROR
      ERROR_NO_GUI
      BAD_PARAMETER
      ERROR_WRITING_DATA
      ERROR_STARTING_VIEWER
      UNKNOWN_DOCUMENT_TYPE
      NOT_SUPPORTED_BY_GUI
      ACCESS_DENIED .
  class-methods STRCMPI
    importing
      !TEXT1 type STRING
      !TEXT2 type STRING
    exporting
      !RESULT type ABAP_BOOL .
  type-pools CNDP .
  type-pools CNTL .
ENDCLASS.



CLASS CL_GUI_FRONTEND_SERVICES IMPLEMENTATION.


method CHECK_GUI_SUPPORT .
*  Ask TITA
  FIELD-SYMBOLS: <F_GUI> TYPE DATA.
    DATA: RC TYPE I,
        xmlstream type string,
        strcomp type string,
        strfeaturename type string,
        strgui type string,
        strPath type string,
        ret_wingui type c,
        ret_platin type c,
        ret_its type c,
        strResult type string,
        streamlength type i,
        R_CODE TYPE ABAP_BOOL.

*--table structure definition for mapping xml content after parsing
*  data: begin of features_record,
*          component(30) type c,
*          featurename(30) type c,
*          value(30) type c,
*      end of features_record.

*--end of table definition-----------------------------------------

  data: features_tab type SFES_FEATURES_TAB_TYPE.

  DATA: features_wa type sfes_features_record_type,
* features_record,
        f_wa type sfes_features_record_type.
* features_record.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    raise NOT_SUPPORTED_BY_GUI.
  endif.


*--get the ixml library--------------------------------------------
  type-pools: ixml.
  class cl_ixml definition load.

  RESULT = ABAP_FALSE.

*-check parameters-------------------------------------------------
  IF FEATURE_NAME IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

  IF COMPONENT IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

*--check for gui, win, platin or its-------------------------------
*  CALL FUNCTION 'GUI_IS_ITS'
*    IMPORTING
*      RETURN = R_CODE.
*  IF R_CODE IS NOT INITIAL.
*    Assign 'web' to <F_GUI>.
*    "    WRITE: / <F_GUI>.
*  ELSE.
*    CALL FUNCTION 'GUI_HAS_JAVABEANS'
*      IMPORTING
*        RETURN = R_CODE.
*    IF R_CODE IS NOT INITIAL.
*      Assign 'plat' to <F_GUI>.
*      "     WRITE: / <F_GUI>.
*    ELSE.
*      CALL FUNCTION 'GUI_HAS_ACTIVEX'
*        IMPORTING
*          RETURN = R_CODE.
*      IF R_CODE IS NOT INITIAL.
*        Assign 'win' to <F_GUI>.
*        "      WRITE: / <F_GUI>.
*      ENDIF.
*    ENDIF.
*  ENDIF.
*
**--end gui check-----------------------------------------------------
*
*--convert inputs to lower case for conformity with xml stream-------
  strcomp = COMPONENT.
  strfeaturename = FEATURE_NAME.
  TRANSLATE strcomp TO LOWER CASE.
  TRANSLATE strfeaturename TO LOWER CASE.
*
*
**--cache insert context definition------------------------------------
*  DATA CONTEXT_ID(32).
*  DATA KEY TYPE eudb-name.
*  DATA WA  TYPE eudb.
*  data rcui(1).
*
**--try to get features_tab from shared memory-------------------------
*  call FUNCTION 'TH_GET_SESSION_ID'
*    IMPORTING
*      SESSION_ID = context_id.
*
*  call function 'GUI_IS_RCUI'
*      importing
*        return = rcui.
*
*  key = context_id.
*
*  if rcui = 'X'.
*    concatenate context_id 'RCUI' into key.
*  endif.
*
*  IMPORT features_tab = features_tab
*  FROM SHARED BUFFER eudb(FE) ID KEY.
*
**error check----------------------------------------------------------
**  if sy-subrc eq 0.
**if succeded, check if table is already filled up---------------------
*  if features_tab is initial.
**if table features_tab from shared memory is not yet filled up--------
**get xml data stream from front end-----------------------------------
*
*    CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_GUI_PROPERTIES
*      CHANGING
*        STREAM                    = xmlstream
*      EXCEPTIONS
*        CNTL_ERROR                = 1
*        GET_GUI_PROPERTIES_FAILED = 2
*        ERROR_NO_GUI              = 3
*        WRONG_PARAMETER           = 4
*        NOT_SUPPORTED_BY_GUI      = 5
*        others                    = 6.
*
*    IF SY-SUBRC <> 0.
*      RESULT = ABAP_FALSE.
*      EXIT.
*    ENDIF.
*
*    streamlength = strlen( xmlstream ).
*    if streamlength <> 0.
*
**undertake the parsing process-----------------------------------------
*
**-- create the main factory
*      data: pixml type ref to if_ixml.
*      pixml = cl_ixml=>create( ).
*
**-- create the initial document
*      data: pdocument type ref to if_ixml_document.
*      pdocument = pixml->create_document( ).
*
**-- create the stream factory
*      data: pstreamfactory type ref to if_ixml_stream_factory.
*      pstreamfactory = pixml->create_stream_factory( ).
*
**-- create a stream for the input (string)
*      data: pistream type ref to if_ixml_istream.
*      data: xml_doc type string value 'hello world!'.
*
*      pistream = pstreamfactory->create_istream_string( xmlstream ).
*
*
**-- create the parser
*      data: pparser type ref to if_ixml_parser.
*      pparser = pixml->create_parser( stream_factory  = pstreamfactory
*                                        istream       = pistream
*                                        document      = pdocument ).
**-- parse the stream
*      if pparser->parse( ) ne 0.
*        if pparser->num_errors( ) ne 0.
**          data: count type i.
**          count = pparser->num_errors( ).
**          write: count, ' parse errors have occured:'.      "#EC NOTEXT
**          data: pparseerror type ref to if_ixml_parse_error,
**                i type i.
**          data: index type i value 0.
**          while index < count.
**            pparseerror = pparser->get_error( index = index ).
**            i = pparseerror->get_line( ).
**            write: 'line: ', i.                             "#EC NOTEXT
**            i = pparseerror->get_column( ).
**            write: 'column: ', i.                           "#EC NOTEXT
**            data: string type string.
**            string = pparseerror->get_reason( ).
**            write: string.
**            index = index + 1.
**          endwhile.
*        endif.
*      endif.
**end of parsing process-------------------------------------------------
*    else.
*      exit.
*    endif.
**data prior to filling up of shared memory table features_tab-----------
*    data: filter1  type ref to if_ixml_node_filter,
*          filter2  type ref to if_ixml_node_filter,
*          filter   type ref to if_ixml_node_filter,
*          iterator type ref to if_ixml_node_iterator,
*          node     type ref to if_ixml_node,
*          node1     type ref to if_ixml_node,
*          str1 type string,
*          str2 type string.
*    filter2  = pdocument->create_filter_attribute( name = <F_GUI>
*                                                  value = 'X' ).
*    iterator = pdocument->create_iterator_filtered( filter2 ).
*
*    node = iterator->get_next( ).
*    while not node is initial.
*      str1 = node->get_name( ).
*      TRANSLATE str1 TO LOWER CASE.
*
*      features_wa-featurename = str1.
*      features_wa-value = 'X'.
*
*      node1 = node->get_parent( ).
*
*      if not node1 is initial.
*        str2 = node1->get_name( ).
*        TRANSLATE str2 TO LOWER CASE.
*
*        features_wa-component = str2.
*      endif.
*
*      APPEND features_wa TO features_tab.
*      node = iterator->get_next( ).
*    endwhile.
*
**
**      data: filter  type ref to if_ixml_node_filter.
**      data: str1 type string,
**            str2 type string,
**            str3 type string.
**
**      data: node type ref to if_ixml_node,
**            node1 type ref to if_ixml_node,
**            node2 type ref to if_ixml_node,
**            nr type I.
***end data
**definition----------------------------------------------------
**
**      filter = pdocument->create_filter_name( name = strgui ).
**      data: iterator type ref to if_ixml_node_iterator.
**      iterator = pdocument->create_iterator_filtered( filter ).
**
**fill table struct for lookup------------------------------------------
**      node = iterator->get_next( ).
**      while not node is initial.
**        nr = node->num_children( ).
**        str1 = node->get_value( ).
**        features_wa-value = str1.
**        node1 = node->get_parent( ).
**        if not node1 is initial.
**          str3 = node1->get_name( ).
**          features_wa-featurename =  str3.
**          node2 = node1->get_parent( ).
**          if not node2 is initial.
**            str2 = node2->get_name( ).
**            features_wa-component = str2.
**          endif.
**        endif.
**        APPEND features_wa TO features_tab.
**        node = iterator->get_next( ).
**      endwhile.
*
**cache insert-----------------------------------------------------------
*
*    EXPORT features_tab          = features_tab
*           TO SHARED BUFFER eudb(FE) ID KEY.
*cache insert ende------------------------------------------------------
*get value from table---------------------------------------------------

  call method GET_FEATURES_TAB RECEIVING features_tab = features_tab
              EXCEPTIONS
              UNKNOWN_ERROR             = 1
              others                    = 2.
  IF sy-subrc <> 0.
    RAISE cntl_error.
    RESULT = ABAP_FALSE.
  ELSE.

    loop at features_tab into f_wa.
      if f_wa-component = strcomp and f_wa-featurename = strfeaturename.
        strResult = f_wa-value.
*        write: / f_wa-value.
        exit.
      endif.
*      write: / f_wa-value.
    endloop.
  ENDIF.
*  else.
**get value from cache if features_tab content data----------------------
*
*    loop at features_tab into f_wa.
*      if f_wa-component = strcomp and f_wa-featurename = strfeaturename.
*        strResult = f_wa-value.
**        write: / f_wa-value.
*        exit.
*      endif.
**      write: / f_wa-value.
*    endloop.
*  endif.
*end of get value from shared memory------------------------------------
*set the return value---------------------------------------------------

  if not strResult is initial.
    RESULT = ABAP_TRUE.
  else.
    RESULT = ABAP_FALSE.
  endif.
*end of set return value------------------------------------------------

*  else.
*if error check fails---------------------------------------------------
*    RAISE CNTL_ERROR.
*  endif.
*end of error check-----------------------------------------------------
endmethod.


METHOD CHECK_OPEN_NEW_WINDOW.

  DATA: ACT_SESSIONS TYPE SM04DIC-COUNTER.
  DATA: MAX_SESSIONS TYPE SM04DIC-COUNTER.
  DATA: IS_ITS TYPE C.

  CALL FUNCTION 'GUI_IS_ITS'
  IMPORTING
    RETURN        = IS_ITS.

  IF IS_ITS IS INITIAL. " SAPGUI for Windows and JavaGUI

* check if we have not reached the max number of sessions
    CALL FUNCTION 'TH_USER_INFO'
    IMPORTING
      ACT_SESSIONS = ACT_SESSIONS
      MAX_SESSIONS = MAX_SESSIONS.

    IF MAX_SESSIONS = ACT_SESSIONS.
      MESSAGE I374(S#).
      RESULT = ABAP_FALSE.
    ELSE.
      RESULT = ABAP_TRUE.
    ENDIF.
  ELSE.
* check if a WebSocket connection is available
* and we can use it to open a second Window.
    IF CL_APC_WS_SESSION_COMMAND=>CHECK( ).
      RESULT = ABAP_TRUE.
    ELSE.
      RESULT = ABAP_FALSE.
      MESSAGE I108(ITS_P).
    ENDIF.

  ENDIF.

ENDMETHOD.


  method CHECK_UI_GUIDELINE.
  data mode type i.

  CALL 'C_GUI_SUPPORT'
       ID 'FEATURE' FIELD 'FIORI_MODE'
       ID 'VALUE' FIELD mode.

  result = abap_undefined.

  case guideline.
    when GUIDELINE_FIORI_2.
       if mode = 1.
         result = abap_true.
       else.
         result = abap_false.
       endif.
    when GUIDELINE_CLASSIC.
        if mode ne 1.
          result = abap_true.
        else.
          result = abap_false.
        endif.
    endcase.

  endmethod.


METHOD CLASS_CONSTRUCTOR .

* ...
  CLASS CL_GUI_CONTROL DEFINITION LOAD.

* check for WWW_ACTIVE at first because attribut ACTIVEX is also set
* by ITS
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
    ERROR_CODE = ERROR_NOT_SUPPORTED_BY_GUI.
  ELSEIF CL_GUI_CONTROL=>JAVABEAN IS NOT INITIAL OR
          CL_GUI_CONTROL=>ACTIVEX IS NOT INITIAL.
* call instance contructor only once
    CREATE OBJECT HANDLE
      EXCEPTIONS OTHERS = 1.
    IF SY-SUBRC NE 0.
      CLEAR HANDLE.
    ENDIF.
  ELSE.
    ERROR_CODE = ERROR_NO_GUI.
  ENDIF.

  FILETYPE_ALL         = ''(000).
  FILETYPE_EXCEL       = ''(001).
  FILETYPE_WORD        = ''(002).
  FILETYPE_TEXT        = ''(003).
  FILETYPE_HTML        = ''(004).
  FILETYPE_RTF         = ''(005).
  FILETYPE_XML         = ''(006).
  FILETYPE_POWERPOINT  = ''(008).

ENDMETHOD.                    "


method CLIPBOARD_EXPORT.
* ...

  DATA: table_ref TYPE REF TO data,
        authority_check_result_i TYPE I.
  FIELD-SYMBOLS <table> TYPE STANDARD TABLE.
  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check permissions------------------------------------------------

   IF no_auth_check = SPACE.
    authority-check object 'S_GUI'
                        ID 'ACTVT'
                     FIELD '61'.
    IF sy-subrc <> 0.
      authority-check object 'S_GUI'
                          ID 'ACTVT'
                       FIELD '02'.

      IF sy-subrc <> 0.
        authority_check_result_i = 1. " RAISE no_authority.
      endif.
    ENDIF.
  ENDIF.

  IF authority_check_result_i <> 0.
    MESSAGE I013(PC) RAISING NO_AUTHORITY.
    EXIT.
  ENDIF.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    CALL FUNCTION 'ITS_CLIPBOARD_EXPORT'
      IMPORTING
        RC       = RC
      TABLES
        DATA     = DATA
      EXCEPTIONS
        OTHERS   = 1.

    IF SY-SUBRC <> 0 OR RC = -1.
      RAISE CNTL_ERROR.
    ENDIF.

    EXIT.

  ENDIF.


* send data to frontend
  CALL FUNCTION 'DP_STRETCH_SIMPLE_TABLE'
    EXPORTING
      copy_lines             = 'X'
    IMPORTING
      stretched_data_ref     = table_ref
    TABLES
      data                   = data
    EXCEPTIONS
      DP_ERROR_MULTIPLE_COLS = 1
      DP_ERROR_NOT_CHARLIKE  = 2.

  IF sy-subrc = 0.
    ASSIGN table_ref->* TO <table>.
  ELSE.
    ASSIGN data TO <table>.
  ENDIF.

  CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
      PROPERTYNAME           = 'ClipBoardDataTable'
    TABLES
      DATA                   = <table>
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_SEND_DATA     = 2
      DP_ERROR_ASSIGN        = 3
      DP_ERROR_INVALID_PARAM = 4
      DP_ERROR_TABNAME       = 5
      OTHERS                 = 6.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* fill file table at frontend
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'ClipboardExport'
      P_COUNT = 0
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0 OR RC = -1.
    RAISE CNTL_ERROR.
  ENDIF.

endmethod.                    "


method CLIPBOARD_IMPORT.
* ...

  DATA: table_ref TYPE REF TO data,
        orig_table_ref TYPE REF TO data.
  FIELD-SYMBOLS <table> TYPE STANDARD TABLE.
  CLASS CL_GUI_CONTROL DEFINITION LOAD .

  DATA line(4096).    "take wide enougth table for transport
  DATA tab like table of line.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    CALL FUNCTION 'ITS_CLIPBOARD_IMPORT'
      IMPORTING
        LENGTH   = LENGTH
      TABLES
        DATA     = DATA
      EXCEPTIONS
        OTHERS   = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    EXIT.

  ENDIF.

  IF NOT DATA[] IS INITIAL.
    CLEAR DATA[]. " it is an importing parameter which needs to be cleared, else appends to prev. data
  ENDIF.

* send data to frontend
  CALL FUNCTION 'DP_STRETCH_SIMPLE_TABLE'
    EXPORTING
      copy_lines             = ' '
    IMPORTING
      stretched_data_ref     = table_ref
    TABLES
      data                   = data
    EXCEPTIONS
      DP_ERROR_MULTIPLE_COLS = 1
      DP_ERROR_NOT_CHARLIKE  = 2.

  IF sy-subrc = 0.
    IF use_data_line_size IS INITIAL.
      ASSIGN tab TO <table>. " just take the very wide table
    ELSE. " use line sizes of the DATA parameter (fallback)
      ASSIGN table_ref->* TO <table>.
    ENDIF.
  ELSE.
    ASSIGN data TO <table>.
  ENDIF.

  CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
      PROPERTYNAME           = 'ClipBoardDataTable'
    TABLES
      DATA                   = <table>
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_SEND_DATA     = 2
      DP_ERROR_ASSIGN        = 3
      DP_ERROR_INVALID_PARAM = 4
      DP_ERROR_TABNAME       = 5
      OTHERS                 = 6.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* fill file table at frontend
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'ClipboardImport'
      P_COUNT = 0
    IMPORTING
      RESULT  = LENGTH
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* get  table from frontend
  CALL FUNCTION 'DP_CONTROL_GET_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      PROPERTYNAME           = 'ClipBoardDataTable'
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
    TABLES
      DATA                   = <table>
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_GET_PROPERTY  = 2
      DP_ERROR_GET_DATA      = 3
      DP_ERROR_INVALID_PARAM = 4
      OTHERS                 = 5.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  GET REFERENCE OF data[]  INTO orig_table_ref.
  GET REFERENCE OF <table> INTO table_ref.

  IF orig_table_ref <> table_ref.
*    data = <table>[].
    FIELD-SYMBOLS <F> type any.
    data l type i.
    DATA dref type ref to data.
*   get length of small table
    CREATE DATA dref like LINE OF data. " this is the table parameter data
    ASSIGN dref->* to <F>.
    DESCRIBE FIELD <F> LENGTH l IN CHARACTER MODE.

    loop at <table> ASSIGNING <F>.
      append <F> to data[].
      SHIFT <F> IN CHARACTER MODE by l PLACES.
      while <f> ne space.
        append <F> to data[].
        SHIFT <F> IN CHARACTER MODE by l PLACES.
      endwhile.
    endloop.
  ENDIF.

endmethod.                    "


METHOD CONSTRUCTOR .

* ...
  data: IsPlatin_Gui type c,
        CLS_ID(64) type C.

* dont create info control on SAPGUI for HTML
* check WWW_ACTIVE IS INITIAL.

*--check for platin_gui------------------------
  CALL FUNCTION 'GUI_HAS_JAVABEANS'
    IMPORTING
      RETURN = IsPlatin_Gui.

  IF IsPlatin_Gui = 'X'.
    CLS_ID = 'SAPINFO'.
  ELSE.
    IF WWW_ACTIVE IS INITIAL.
       CLS_ID = 'SAPGUI.InfoCtrl.1'.
    ENDIF.
  ENDIF.

  CALL METHOD SUPER->CONSTRUCTOR
    EXPORTING
      CLSID  = CLS_ID
    EXCEPTIONS
      OTHERS = 1.

  if sy-subrc <> 0.
    raise CNTL_ERROR.
  endif.

ENDMETHOD.                    "


METHOD DIRECTORY_BROWSE .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* special handling for SAPGUI for HTML
  IF NOT cl_gui_control=>www_active IS INITIAL.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
    CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

    CALL FUNCTION 'ITS_DIRECTORY_GET'
      EXPORTING
        PATH   = INITIAL_FOLDER
        TITLE  = WINDOW_TITLE
      IMPORTING
        RETURN = SELECTED_FOLDER
      EXCEPTIONS
        SELECTION_ERROR        = 1
        SELECTION_CANCEL       = 2
        OTHERS                 = 3.

    CASE SY-SUBRC.
      WHEN 0.
      WHEN 2.
      WHEN OTHERS.
        RAISE CNTL_ERROR.
    ENDCASE.

    EXIT.
  ENDIF.

* call BrowseForFolder

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'BrowseForFolder'
      P_COUNT    = 2
      P1         = WINDOW_TITLE
      P2         = INITIAL_FOLDER
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = SELECTED_FOLDER
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
  CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "DIRECTORY_BROWSE


METHOD DIRECTORY_CREATE .

*---------------------------------------------------------------------*
*       METHOD DIRECTORY_CREATE                                       *
*---------------------------------------------------------------------*
*       ........                                                      *
*---------------------------------------------------------------------*
* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

  IF DIRECTORY IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    CALL FUNCTION 'ITS_DIRECTORY_CREATE'
      EXPORTING
        DIRECTORY    = DIRECTORY
      IMPORTING
        RC           = RC
      EXCEPTIONS
        OTHERS       = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'CreateDirectory'
        P1         = DIRECTORY
        P_COUNT    = 1
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = RC
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

  IF RC <> 0.
    CASE RC.
      WHEN 3.       "ERROR_PATH_NOT_FOUND
        RAISE PATH_NOT_FOUND.
      WHEN 5.       " ERROR_ACCESS_DENIED
        RAISE DIRECTORY_ACCESS_DENIED.
      WHEN 183.     " ERROR_ALREADY_EXISTS
        RAISE DIRECTORY_ALREADY_EXISTS.
      WHEN OTHERS.
        RAISE UNKNOWN_ERROR.
    ENDCASE.
  ENDIF.

ENDMETHOD.                    "DIRECTORY_CREATE


METHOD DIRECTORY_DELETE .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

  IF DIRECTORY IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    CALL FUNCTION 'ITS_DIRECTORY_DELETE'
      EXPORTING
        DIRECTORY    = DIRECTORY
      IMPORTING
        RC           = RC
      EXCEPTIONS
        OTHERS       = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'RemoveDirectory'
        P1         = DIRECTORY
        P_COUNT    = 1
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = RC
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

  IF RC <> 0.
    CASE RC.
      WHEN 2 OR 3.  "ERROR_PATH_NOT_FOUND
        RAISE PATH_NOT_FOUND.
      WHEN 5.       " ERROR_ACCESS_DENIED
        RAISE DIRECTORY_ACCESS_DENIED.
      WHEN OTHERS.
        RAISE UNKNOWN_ERROR.
    ENDCASE.
  ENDIF.

ENDMETHOD.                    "


method DIRECTORY_EXIST.
* ...
  DATA RC Type I.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*check constructor error code------------------------------------

  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

  IF DIRECTORY IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

*special handling for SAPGUI for HTML----------------------------

  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    DATA filename(4096).
    filename = directory.

    CALL FUNCTION 'ITS_QUERY'
      EXPORTING
        filename = filename
        query    = 'DE'
      IMPORTING
        return   = rc.

    IF rc IS INITIAL.
      RESULT = ABAP_FALSE.
    ELSE.
      RESULT = ABAP_TRUE.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'DirectoryExists'
        P1      = DIRECTORY
        P_COUNT = 1
      IMPORTING
        RESULT  = RC
      EXCEPTIONS
        OTHERS  = 1.

CALL METHOD CL_GUI_CFW=>FLUSH
  EXCEPTIONS
    CNTL_SYSTEM_ERROR = 1
    CNTL_ERROR        = 2
    others            = 3 .

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CASE RC.
      WHEN 0.
        RESULT = ABAP_FALSE.
      WHEN 1.
        RESULT = ABAP_TRUE.
      WHEN OTHERS.
        RAISE CNTL_ERROR.
    ENDCASE.
  ENDIF.
endmethod.                    "


METHOD DIRECTORY_GET_CURRENT .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD.

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* special handling for SAPGUI for HTML
  IF WWW_ACTIVE IS NOT initial.

    CALL FUNCTION 'ITS_QUERY'
      EXPORTING
*   ENVIRONMENT       =
*   FILENAME          =
        QUERY             = 'CD'
     IMPORTING
       RETURN            =  CURRENT_DIRECTORY.
    EXIT.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetCurrentDirectory'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = CURRENT_DIRECTORY
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "DIRECTORY_GET_CURRENT


METHOD directory_list_files .
* ...

  DATA: wa_file_table TYPE file_info,
        tab TYPE STANDARD TABLE OF file_info.
  DATA  len TYPE i.
  DATA  separator_symbol TYPE c.

*-check if valid GUI is available----------------------------------
  IF is_valid_handle( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE not_supported_by_gui.
  ENDIF.

* check parameters
  IF ( directory IS INITIAL ) OR
     ( NOT files_only IS INITIAL AND
       NOT directories_only IS INITIAL ).
    RAISE wrong_parameter.
  ENDIF.

* check for last \
  len = strlen( directory ).
  len = len - 1.

  IF cl_gui_control=>www_active IS INITIAL.

    CALL METHOD cl_gui_frontend_services=>get_file_separator
      CHANGING
        file_separator       = separator_symbol
      EXCEPTIONS
        not_supported_by_gui = 1
        error_no_gui         = 2
        cntl_error           = 3
        OTHERS               = 4.

    CASE sy-subrc.
      WHEN 0.
      WHEN 1.       RAISE not_supported_by_gui.
      WHEN 2.       RAISE error_no_gui.
      WHEN OTHERS.  RAISE cntl_error.
    ENDCASE.

*   dont add a '\' when called from FILE_EXIST
    IF icall = 1.
      icall = 0.
    ELSE.
      IF NOT directory+len(1) = separator_symbol.
        CONCATENATE directory separator_symbol INTO directory.
      ENDIF.
    ENDIF.
  ENDIF.

*
  IF NOT files_only IS INITIAL.
    files_only = 'X'.
  ELSEIF NOT directories_only IS INITIAL.
    directories_only = 'X'.
  ENDIF.

* special handling for SAPGUI for HTML
  IF NOT cl_gui_control=>www_active IS INITIAL.

    CALL FUNCTION 'ITS_DIRECTORY_LIST_FILES'
      EXPORTING
        directory        = directory
        filter           = filter
      IMPORTING
        count            = count
      TABLES
        file_table       = tab
      EXCEPTIONS
        selection_error  = 1
        selection_cancel = 2
        OTHERS           = 3.

    CASE sy-subrc.
      WHEN 0.
      WHEN 2.
      WHEN OTHERS.
        RAISE cntl_error.
    ENDCASE.

  ELSE.

*   send data to frondend
    CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
      EXPORTING
        h_cntl                 = handle->h_control
        medium                 = cndp_medium_r3table
        propertyname           = 'R3TABLE'
      TABLES
        data                   = tab
      EXCEPTIONS
        dp_error_create        = 1
        dp_error_send_data     = 2
        dp_error_assign        = 3
        dp_error_invalid_param = 4
        dp_error_tabname       = 5
        OTHERS                 = 6.

    IF sy-subrc <> 0.
      RAISE cntl_error.
    ENDIF.

*   fill file table at frontend
    CALL METHOD handle->call_method
      EXPORTING
        method  = 'LISTFILES'
        p_count = 2
        p1      = directory
        p2      = filter
      IMPORTING
        result  = count
      EXCEPTIONS
        OTHERS  = 1.

    IF sy-subrc <> 0.
      RAISE cntl_error.
    ENDIF.

*   get file table from frontend
    CALL FUNCTION 'DP_CONTROL_GET_TABLE'
      EXPORTING
        h_cntl                 = handle->h_control
        propertyname           = 'R3TABLE'
        medium                 = cndp_medium_r3table
      TABLES
        data                   = tab
      EXCEPTIONS
        dp_error_create        = 1
        dp_error_get_property  = 2
        dp_error_get_data      = 3
        dp_error_invalid_param = 4
        OTHERS                 = 5.

    IF sy-subrc <> 0.
      RAISE cntl_error.
    ENDIF.

  ENDIF.

* filter file table and set count
  IF NOT files_only IS INITIAL.
    LOOP AT tab INTO wa_file_table.
      IF wa_file_table-isdir = 0.
        APPEND wa_file_table TO file_table .
      ENDIF.
    ENDLOOP.
  ELSEIF NOT directories_only IS INITIAL.
    LOOP AT tab INTO wa_file_table.
      IF wa_file_table-isdir = 1.
        APPEND wa_file_table TO file_table .
      ENDIF.
    ENDLOOP.
  ELSE.
    LOOP AT tab INTO wa_file_table.
      APPEND wa_file_table TO file_table .
    ENDLOOP.
  ENDIF.

* determine number of files/directories
  DESCRIBE TABLE file_table LINES count.

ENDMETHOD.                    "


METHOD directory_list_files_ext .
* ...

  DATA: wa_file_table TYPE file_info_ext,
        tab           TYPE STANDARD TABLE OF file_info_ext,
        tab_fallback  TYPE STANDARD TABLE OF file_info.
  DATA  len TYPE i.
  DATA  separator_symbol TYPE c.
  DATA: ret_val                  TYPE abap_bool,
        use_fallback             TYPE abap_bool VALUE IS INITIAL,
        frontend_method_name(42) VALUE 'ListFilesExt'.

*-check if valid GUI is available----------------------------------
  IF is_valid_handle( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE not_supported_by_gui.
  ENDIF.

* check parameters
  IF ( directory IS INITIAL ) OR
     ( NOT files_only IS INITIAL AND
       NOT directories_only IS INITIAL ).
    RAISE wrong_parameter.
  ENDIF.

* check for last \
  len = strlen( directory ).
  len = len - 1.

  IF cl_gui_control=>www_active IS INITIAL.

    CALL METHOD cl_gui_frontend_services=>get_file_separator
      CHANGING
        file_separator       = separator_symbol
      EXCEPTIONS
        not_supported_by_gui = 1
        error_no_gui         = 2
        cntl_error           = 3
        OTHERS               = 4.

    CASE sy-subrc.
      WHEN 0.
      WHEN 1.       RAISE not_supported_by_gui.
      WHEN 2.       RAISE error_no_gui.
      WHEN OTHERS.  RAISE cntl_error.
    ENDCASE.

*   dont add a '\' when called from FILE_EXIST
    IF icall = 1.
      icall = 0.
    ELSE.
      IF NOT directory+len(1) = separator_symbol.
        CONCATENATE directory separator_symbol INTO directory.
      ENDIF.
    ENDIF.
  ENDIF.

*
  IF NOT files_only IS INITIAL.
    files_only = 'X'.
  ELSEIF NOT directories_only IS INITIAL.
    directories_only = 'X'.
  ENDIF.

*check if the method is supported by the windows gui, use fallback if it is not
  CALL METHOD cl_gui_frontend_services=>check_gui_support
    EXPORTING
      component            = 'sapinfocntl'
      feature_name         = 'DIRECTORY_LIST_FILES_EXT'
    RECEIVING
      result               = ret_val
    EXCEPTIONS
      cntl_error           = 1
      error_no_gui         = 2
      wrong_parameter      = 3
      not_supported_by_gui = 4
      unknown_error        = 5
      OTHERS               = 6.

  IF sy-subrc <> 0.
    ret_val = abap_false.
  ENDIF.

  IF ret_val IS INITIAL.
    use_fallback = abap_true.
    " "fallback" means: if the frontend do not support this method, we simulate the older DIRECTORY_LIST_FILES method
  ENDIF.

* special handling for SAPGUI for HTML
  IF NOT cl_gui_control=>www_active IS INITIAL.

    IF use_fallback IS INITIAL.

      CALL FUNCTION 'ITS_DIRECTORY_LIST_FILES'
        EXPORTING
          directory        = directory
          filter           = filter
          ret_long         = ret_val
        IMPORTING
          count            = count
        TABLES
          file_table       = tab
        EXCEPTIONS
          selection_error  = 1
          selection_cancel = 2
          OTHERS           = 3.

      CASE sy-subrc.
        WHEN 0.
        WHEN 2.
        WHEN OTHERS.
          RAISE cntl_error.
      ENDCASE.

    ELSE. " use fallback

      CALL FUNCTION 'ITS_DIRECTORY_LIST_FILES'
        EXPORTING
          directory        = directory
          filter           = filter
          ret_long         = ret_val
        IMPORTING
          count            = count
        TABLES
          file_table       = tab_fallback
        EXCEPTIONS
          selection_error  = 1
          selection_cancel = 2
          OTHERS           = 3.

      CASE sy-subrc.
        WHEN 0.
        WHEN 2.
        WHEN OTHERS.
          RAISE cntl_error.
      ENDCASE.

    ENDIF.

  ELSE.

*use older c++ method if the new one is not supported by the windows gui
    IF use_fallback IS INITIAL.

*   send data to frondend
      CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
        EXPORTING
          h_cntl                 = handle->h_control
          medium                 = cndp_medium_r3table
          propertyname           = 'R3TABLE'
        TABLES
          data                   = tab
        EXCEPTIONS
          dp_error_create        = 1
          dp_error_send_data     = 2
          dp_error_assign        = 3
          dp_error_invalid_param = 4
          dp_error_tabname       = 5
          OTHERS                 = 6.

      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

    ELSE. " use fallback

      frontend_method_name = 'ListFiles'.

*   send data to frondend
      CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
        EXPORTING
          h_cntl                 = handle->h_control
          medium                 = cndp_medium_r3table
          propertyname           = 'R3TABLE'
        TABLES
          data                   = tab_fallback
        EXCEPTIONS
          dp_error_create        = 1
          dp_error_send_data     = 2
          dp_error_assign        = 3
          dp_error_invalid_param = 4
          dp_error_tabname       = 5
          OTHERS                 = 6.

      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

    ENDIF.

*   fill file table at frontend
    CALL METHOD handle->call_method
      EXPORTING
        method  = frontend_method_name
        p_count = 2
        p1      = directory
        p2      = filter
      IMPORTING
        result  = count
      EXCEPTIONS
        OTHERS  = 1.

    IF sy-subrc <> 0.
      RAISE cntl_error.
    ENDIF.

    IF use_fallback IS INITIAL.

*   get file table from frontend
      CALL FUNCTION 'DP_CONTROL_GET_TABLE'
        EXPORTING
          h_cntl                 = handle->h_control
          propertyname           = 'R3TABLE'
          medium                 = cndp_medium_r3table
        TABLES
          data                   = tab
        EXCEPTIONS
          dp_error_create        = 1
          dp_error_get_property  = 2
          dp_error_get_data      = 3
          dp_error_invalid_param = 4
          OTHERS                 = 5.

      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

    ELSE. " use fallback

*   get file table from frontend
      CALL FUNCTION 'DP_CONTROL_GET_TABLE'
        EXPORTING
          h_cntl                 = handle->h_control
          propertyname           = 'R3TABLE'
          medium                 = cndp_medium_r3table
        TABLES
          data                   = tab_fallback
        EXCEPTIONS
          dp_error_create        = 1
          dp_error_get_property  = 2
          dp_error_get_data      = 3
          dp_error_invalid_param = 4
          OTHERS                 = 5.

      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

    ENDIF.

  ENDIF.

  IF use_fallback IS NOT INITIAL.
    MOVE-CORRESPONDING tab_fallback TO tab. " transfer fallback table into the original table
  ENDIF.

* filter file table and set count
  IF NOT files_only IS INITIAL.
    LOOP AT tab INTO wa_file_table.
      IF wa_file_table-isdir = 0.
        APPEND wa_file_table TO file_table .
      ENDIF.
    ENDLOOP.
  ELSEIF NOT directories_only IS INITIAL.
    LOOP AT tab INTO wa_file_table.
      IF wa_file_table-isdir = 1.
        APPEND wa_file_table TO file_table .
      ENDIF.
    ENDLOOP.
  ELSE.
    LOOP AT tab INTO wa_file_table.
      APPEND wa_file_table TO file_table .
    ENDLOOP.
  ENDIF.

* determine number of files/directories
  DESCRIBE TABLE file_table LINES count.

ENDMETHOD.                    "


METHOD DIRECTORY_SET_CURRENT .

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.


  IF CURRENT_DIRECTORY IS INITIAL.
    RAISE DIRECTORY_SET_CURRENT_FAILED.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'SetCurrentDirectory'
      P1      = CURRENT_DIRECTORY
      P_COUNT = 1
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "


method DISABLEHISTORYFORFIELD.

  DATA : feature_supported_b TYPE ABAP_BOOL,
         gui_available_b TYPE CHAR1,
         RET_VALUE TYPE I,
         DISABLED        TYPE I.

  "-initial checks------------------------------------------------------
  CALL FUNCTION 'GUI_IS_AVAILABLE'     " check if running in batch, etc.
    IMPORTING
      return = gui_available_b.

  IF gui_available_b IS INITIAL.
    RAISE ERROR_NO_GUI.
  ENDIF.

  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING                          " check GUI support
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'DISABLEHISTORYFORFIELD'
    RECEIVING
      RESULT               = feature_supported_b
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF ( SY-SUBRC <> 0 ) OR ( feature_supported_b = ABAP_FALSE ).
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF BDISABLED IS INITIAL.
    DISABLED = 0.
  ELSE.
    DISABLED = 1.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'DisableHistoryForField'
      P_COUNT = 2
      P1      = FIELDNAME
      P2      = DISABLED
    IMPORTING
      RESULT  = RC.

  CALL METHOD CL_GUI_CFW=>FLUSH.
  IF SY-SUBRC <> 0.
    raise CNTL_ERROR.
  endif.

  case RC.
    when 1.
      raise FIELD_NOT_FOUND.
    when 2.
      raise DISABLEHISTORYFORFIELD_FAILED.
    when 3.
      raise CNTL_ERROR.
    when 4.
      raise UNABLE_TO_DISABLE_FIELD.
  endcase.

endmethod.                    "DISABLEHISTORYFORFIELD


METHOD ENVIRONMENT_GET_VARIABLE .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetEnvVariable'
      P1         = VARIABLE
      P_COUNT    = 1
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = VALUE
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "


METHOD ENVIRONMENT_SET_VARIABLE .

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF VARIABLE IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'SetEnvVariable'
      P1         = VARIABLE
      P2         = VALUE
      P_COUNT    = 2
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = RC
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "


METHOD execute.
* ...

  DATA: name         TYPE string, show_command TYPE i VALUE 5, rc TYPE i.
  DATA: command,
        synflag.

  CLASS cl_gui_control DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF is_valid_handle( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE not_supported_by_gui.
  ENDIF.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
  IF synchronous = 'X'.
    CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.
  ENDIF.

* show command flags for ShellExecute
* SW_SHOWNORMAL       1
* SW_SHOWMINIMIZED    2
* SW_SHOWMAXIMIZED    3
* SW_SHOWNOACTIVATE   4
* SW_SHOW             5
* SW_SHOWMINNOACTIVE  7
* SW_SHOWNA           8
* SW_SHOWDEFAULT      10

* check parameter
  IF ( document IS NOT INITIAL AND application IS NOT INITIAL ) OR
     ( document IS NOT INITIAL AND parameter IS NOT INITIAL ) OR
     ( maximized IS NOT INITIAL AND minimized IS NOT INITIAL ).
    RAISE bad_parameter.
  ENDIF.

  IF document IS NOT INITIAL.
    name  = document.
    CLEAR parameter.
  ENDIF.
  IF application IS NOT INITIAL.
    name = application.
  ENDIF.
  IF minimized IS NOT INITIAL.
    show_command = 2.
  ELSEIF maximized IS NOT INITIAL.
    show_command = 3.
  ENDIF.

*special handling for SAPGUI for HTML.
  IF www_active IS NOT INITIAL.

    IF synchronous IS NOT INITIAL.
      RAISE not_supported_by_gui.
    ENDIF.

    DATA: retcode.
    DATA: prg TYPE string.
    DATA: cmd TYPE string.

    IF document IS NOT INITIAL.
      cmd = document.
      prg = ''.
    ELSE.
      cmd = parameter.
      prg = application.
    ENDIF.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
    IF synchronous = 'X'.
      CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.
    ENDIF.

    CALL FUNCTION 'ITS_EXECUTE'
      EXPORTING
        cd                 = default_directory
        commandline        = cmd
        program            = prg
        inform             = synchronous
*       PROGRAM            = ' '
*       STAT               = ' '
*       WINID              = ' '
*       OSMAC_SCRIPT       = ' '
*       OSMAC_CREATOR      = ' '
*       WIN16_EXT          = ' '
*       EXEC_RC            = ' '
        operation          = operation
      IMPORTING
        rbuff              = retcode
      EXCEPTIONS
        frontend_error     = 1
        prog_not_found     = 2
        gui_refuse_execute = 3
        OTHERS             = 4.

    IF sy-subrc <> 0.
      CASE sy-subrc.
        WHEN 2.
          RAISE file_not_found.
        WHEN OTHERS.
          RAISE error_execute_failed.
      ENDCASE.
    ENDIF.

  ELSE.

    IF javabean IS NOT INITIAL.

      " we might throw an exception later, so flush to preserve
      " the results of the current automation call list

      CALL METHOD cl_gui_cfw=>flush.

      CALL METHOD handle->call_method
        EXPORTING
          method     = 'openDocumentOrApplication'
          p1         = document
          p2         = application
          p3         = parameter
          p4         = default_directory
          p5         = maximized
          p6         = minimized
          p7         = synchronous
          p8         = operation
          p_count    = 8
          queue_only = ' '
        IMPORTING
          result     = rc
        EXCEPTIONS
          OTHERS     = 1.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
      IF synchronous = 'X'.
        CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.
      ENDIF.

      CALL METHOD cl_gui_cfw=>flush
        EXCEPTIONS
          cntl_error = 1
          OTHERS     = 2.
      IF sy-subrc = 0.
        IF rc <> 0.
          CASE rc.
            WHEN 1. " unkown application for mime type
              .   RAISE file_extension_unknown.
            WHEN 2. " unkown mime type for document
              RAISE file_extension_unknown.
            WHEN 3. " document not found
              RAISE path_not_found.
            WHEN 4. " application not found
              RAISE error_execute_failed.
            WHEN 5. " illegal application
              RAISE error_execute_failed.
            WHEN 6. " general error on execute
              RAISE error_execute_failed.
            WHEN 7. " synchronous execution interrupted
              RAISE synchronous_failed.
            WHEN OTHERS.
              RAISE error_execute_failed.
          ENDCASE.
        ELSE.
          rc = 42.
        ENDIF.
      ENDIF.
    ELSE.
* Check if the application should run synchnously, EXECUTE method
* returns the application terminates
      IF synchronous IS NOT INITIAL.


* execute document/application
        CALL METHOD handle->call_method
          EXPORTING
            method     = 'ShellExecuteEx'
            p1         = operation
            p2         = name
            p3         = parameter
            p4         = default_directory
            p5         = show_command
            p6         = 1
            p_count    = 6
            queue_only = ' '
          IMPORTING
            result     = rc
          EXCEPTIONS
            OTHERS     = 1.

      ELSE.

* execute document/application
        CALL METHOD handle->call_method
          EXPORTING
            method     = 'ShellExecute'
            p1         = operation
            p2         = name
            p3         = parameter
            p4         = default_directory
            p5         = show_command
            p_count    = 5
            queue_only = ' '
          IMPORTING
            result     = rc
          EXCEPTIONS
            OTHERS     = 1.

      ENDIF.

      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
      IF synchronous = 'X'.
        CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.
      ENDIF.

      CALL METHOD cl_gui_cfw=>flush
        EXCEPTIONS
          cntl_system_error = 1
          cntl_error        = 2
          OTHERS            = 3.
      IF sy-subrc <> 0.
        RAISE cntl_error.
      ENDIF.

    ENDIF.
* Error codes returned by ShellExecute
*0          The operating system is out of memory or resources.
*SE_ERR_FNF                      2       file not found
*SE_ERR_PNF                      3       path not found
*SE_ERR_ACCESSDENIED             5       access denied
*SE_ERR_OOM                      8       out of memory
*SE_ERR_DLLNOTFOUND              32
*
*SE_ERR_SHARE                    26
*SE_ERR_ASSOCINCOMPLETE          27
*SE_ERR_DDETIMEOUT               28
*SE_ERR_DDEFAIL                  29
*SE_ERR_DDEBUSY                  30
*SE_ERR_NOASSOC                  31

    IF rc < 32.
      CASE rc.
        WHEN 0.
          RAISE synchronous_failed.
        WHEN 2.
          RAISE file_not_found.
        WHEN 3.
          RAISE path_not_found.
        WHEN 27 OR 31.
          RAISE file_extension_unknown.
        WHEN OTHERS.
          RAISE error_execute_failed.
      ENDCASE.
    ENDIF.
  ENDIF.
ENDMETHOD.                    "


method FILE_COPY.
* ...
  DATA: RC TYPE ABAP_BOOL,
        MODE TYPE I,
        RETURN_CODE TYPE I.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF SOURCE IS INITIAL OR DESTINATION IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

  IF SOURCE = DESTINATION.
    RETURN.
  ENDIF.

* check if source exists

  CALL METHOD CL_GUI_FRONTEND_SERVICES=>FILE_EXIST
    EXPORTING
      FILE            = SOURCE
    RECEIVING
      RESULT          = RC
    EXCEPTIONS
      CNTL_ERROR      = 1
      ERROR_NO_GUI    = 2
      WRONG_PARAMETER = 3
      others          = 4.
  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF RC IS INITIAL.
    RAISE FILE_NOT_FOUND.
  ENDIF.

  IF OVERWRITE IS INITIAL.
    MODE = 0.
  ELSE.
    MODE = 1.
  ENDIF.

* copy

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    CALL FUNCTION 'ITS_FILE_COPY'
      EXPORTING
        SOURCE       = SOURCE
        DESTINATION  = DESTINATION
        MODE         = MODE
      IMPORTING
        RC           = RC
      EXCEPTIONS
        OTHERS       = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'FileCopy'
        P1         = SOURCE
        P2         = DESTINATION
        P3         = MODE
        P_COUNT    = 3
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = RETURN_CODE
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

  CASE RETURN_CODE.
    WHEN 0.
      RETURN.
    WHEN 2.
      RAISE FILE_NOT_FOUND.
    WHEN 3.
      RAISE PATH_NOT_FOUND.
    WHEN 5 OR 32.
      RAISE ACCESS_DENIED.
    WHEN 19.
      RAISE DISK_WRITE_PROTECT.
    WHEN 21.
      RAISE DRIVE_NOT_READY.
    WHEN 80.
      RAISE DESTINATION_EXISTS.
    WHEN 112.
      RAISE DISK_FULL.
    WHEN OTHERS.
      RAISE UNKNOWN_ERROR.
  ENDCASE.
endmethod.                    "


METHOD FILE_DELETE .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* check parameter
  IF FILENAME IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

* special handling for SAPGUI for HTML
  IF cl_gui_control=>www_active IS NOT INITIAL.
    CALL FUNCTION 'ITS_FILE_DELETE'
      EXPORTING
        file   = filename
      IMPORTING
        RETURN = RC
    EXCEPTIONS
      OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'DeleteFile'
        P1         = FILENAME
        P_COUNT    = 1
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = RC
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

  IF RC <> 0.
    CASE RC.
      WHEN 2 OR 3.        "ERROR_FILE_NOT_FOUND
        RAISE FILE_NOT_FOUND.
      WHEN 5 OR 32.       " ERROR_ACCESS_DENIED
        " ERROR_SHARING_VIOLATION
        RAISE ACCESS_DENIED.
      WHEN OTHERS.
        RAISE UNKNOWN_ERROR.
    ENDCASE.
  ENDIF.

ENDMETHOD.                    "


method FILE_EXIST.
* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* check parameter, wild characters not allowed
  IF FILE IS INITIAL OR FILE CA '*<>|"'.
  MESSAGE 'WRONG PARAMETER: FILE_NAME'(011) TYPE 'I' RAISING WRONG_PARAMETER.
    EXIT.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    DATA: rc type i, filename(4096) type C.
    filename = file.
    CALL FUNCTION 'ITS_QUERY'
      EXPORTING
        filename = FILEname
        query    = 'FE'
      IMPORTING
        return   = rc.

    IF rc IS INITIAL.
      RESULT = ABAP_FALSE.
    ELSE.
      RESULT = ABAP_TRUE.
    ENDIF.

  ELSE.

    DATA: filetab type table of FILE_INFO,
          count type i.

* force DIRECTORY_LIST_FILES not to add a '\'
    ICALL = 1.

    CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_LIST_FILES
      EXPORTING
        DIRECTORY                   = FILE
        FILTER                      = ''
        FILES_ONLY                  = 'X'
*    DIRECTORIES_ONLY            = 'X'
      CHANGING
        FILE_TABLE                  = filetab
        COUNT                       = count
      EXCEPTIONS
        CNTL_ERROR                  = 1
        DIRECTORY_LIST_FILES_FAILED = 2
        WRONG_PARAMETER             = 3
        ERROR_NO_GUI                = 4
        others                      = 5.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    IF COUNT = 0.
      RESULT = ABAP_FALSE.
    ELSE.
      RESULT = ABAP_TRUE.
    ENDIF.
  ENDIF.


endmethod.                    "


method FILE_GET_ATTRIBUTES .
*---------------------------------------------------------------------*
*  METHOD FILE_GET_ATTRIBUTES
*---------------------------------------------------------------------*
*
*---------------------------------------------------------------------*

  DATA: L_NORMAL TYPE I,
        L_READONLY TYPE I,
        L_HIDDEN TYPE I,
        L_ARCHIVE TYPE I.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF FILENAME IS INITIAL OR
     ( NORMAL IS NOT SUPPLIED   AND
       READONLY IS NOT supplied  AND
       HIDDEN IS NOT SUPPLIED   AND
       ARCHIVE IS NOT SUPPLIED ).

    RAISE WRONG_PARAMETER.
  ENDIF.

* attribute normal
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'GetFileAttribute'
      P1      = FILENAME
      P2      = 1
      P_COUNT = 2
    IMPORTING
      RESULT  = L_NORMAL
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* attribute readonly
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'GetFileAttribute'
      P1      = FILENAME
      P2      = 2
      P_COUNT = 2
    IMPORTING
      RESULT  = L_READONLY
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* attribute hidden
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'GetFileAttribute'
      P1      = FILENAME
      P2      = 3
      P_COUNT = 2
    IMPORTING
      RESULT  = L_HIDDEN
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* attribute archive
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'GetFileAttribute'
      P1      = FILENAME
      P2      = 4
      P_COUNT = 2
    IMPORTING
      RESULT  = L_ARCHIVE
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF L_NORMAL = -1 OR L_READONLY = -1 OR
     L_HIDDEN = -1 OR L_ARCHIVE = -1.
    RAISE FILE_GET_ATTRIBUTES_FAILED.
  ENDIF.

  IF NORMAL IS SUPPLIED.
    IF L_NORMAL = 1.
      NORMAL = 'X'.
    ENDIF.
  ENDIF.

  IF READONLY IS SUPPLIED.
    IF L_READONLY = 1.
      READONLY = 'X'.
    ENDIF.
  ENDIF.

  IF HIDDEN IS SUPPLIED.
    IF L_HIDDEN = 1.
      HIDDEN = 'X'.
    ENDIF.
  ENDIF.

  IF ARCHIVE IS SUPPLIED.
    IF L_ARCHIVE = 1.
      ARCHIVE = 'X'.
    ENDIF.
  ENDIF.

endmethod.                    "FILE_GET_ATTRIBUTES


METHOD FILE_GET_SIZE .

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* check parameter
  IF FILE_NAME IS INITIAL.
    RAISE FILE_GET_SIZE_FAILED.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    DATA: rc(10) type c, filename(4096) type C.

   filename = file_name.
    CALL FUNCTION 'ITS_QUERY'
      EXPORTING
        filename = FILENAME
        query    = 'FL'
      IMPORTING
        return   = FILE_SIZE.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'GetFileSize'
        P1         = FILE_NAME
        P_COUNT    = 1
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = FILE_SIZE
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "


METHOD file_get_size_long .

* ...

  CLASS cl_gui_control DEFINITION LOAD .

  DATA: ret_val                  TYPE abap_bool,
        frontend_method_name(42) VALUE 'GetFileSizeLong'.

*-check if valid GUI is available----------------------------------
  IF is_valid_handle( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE not_supported_by_gui.
  ENDIF.

* check parameter
  IF file_name IS INITIAL.
    RAISE file_get_size_failed.
  ENDIF.


*check if the method is supported by the windows gui
  CALL METHOD cl_gui_frontend_services=>check_gui_support
    EXPORTING
      component            = 'sapinfocntl'
      feature_name         = 'FILE_GET_SIZE_LONG'
    RECEIVING
      result               = ret_val
    EXCEPTIONS
      cntl_error           = 1
      error_no_gui         = 2
      wrong_parameter      = 3
      not_supported_by_gui = 4
      unknown_error        = 5
      OTHERS               = 6.

  IF sy-subrc <> 0.
    ret_val = abap_false.
  ENDIF.

* special handling for SAPGUI for HTML
  IF cl_gui_control=>www_active IS NOT INITIAL.

    DATA: rc(10)         TYPE c, filename(4096) TYPE c.

    filename = file_name.
    CALL FUNCTION 'ITS_QUERY'
      EXPORTING
        filename = filename
        query    = 'FL'
        ret_long = ret_val
      IMPORTING
        return   = file_size.

  ELSE.

*use older c++ method if the new one is not supported by the windows gui
    IF ret_val IS INITIAL.
      frontend_method_name = 'GetFileSize'.
    ENDIF.

    CALL METHOD handle->call_method
      EXPORTING
        method     = frontend_method_name
        p1         = file_name
        p_count    = 1
        queue_only = ' '
      IMPORTING
        result     = file_size
      EXCEPTIONS
        OTHERS     = 1.

    IF sy-subrc <> 0.
      RAISE cntl_error.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "


method FILE_GET_VERSION.
* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF FILENAME IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetFileInfo'
      P1         = FILENAME
      P2         = 1
      P_COUNT    = 2
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = VERSION
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.


endmethod.                    "


METHOD FILE_OPEN_DIALOG .

* ...
  DATA: MULTISEL TYPE I,
        BWITHENCODING TYPE I.
  DATA: FILTER TYPE STRING,
        STR_ENCODING TYPE STRING.
  DATA: L_RESULT TYPE FILE_TABLE,
        FIELDLEN TYPE I,
        NO_ROWS  TYPE I,
        RET_VAL  TYPE ABAP_BOOL,
        table_ref TYPE REF TO data,
        orig_table_ref TYPE REF TO data.
  FIELD-SYMBOLS <table> TYPE STANDARD TABLE.

  DATA : DL_PATH TYPE STRING,
         UPL_PATH TYPE STRING,
         RCCU  TYPE I,
         RCLM  TYPE I,
         FULLPATH type string,
         filename(1024),
         RT_VALUE TYPE ABAP_BOOL.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* Get the initial directory for upload if not set.......................
  IF INITIAL_DIRECTORY EQ SPACE.

    CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_UPLOAD_DOWNLOAD_PATH
      CHANGING
        UPLOAD_PATH                 = UPL_PATH
        DOWNLOAD_PATH               = DL_PATH
      EXCEPTIONS
        CNTL_ERROR                  = 1
        ERROR_NO_GUI                = 2
        NOT_SUPPORTED_BY_GUI        = 3
        GUI_UPLOAD_DOWNLOAD_PATH    = 4
        UPLOAD_DOWNLOAD_PATH_FAILED = 5
        others                      = 6.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    IF UPL_PATH IS NOT INITIAL.
      INITIAL_DIRECTORY = UPL_PATH.
    ENDIF.
  ENDIF.
* end initial directory.................................................

* verify multiselecten flag
  IF NOT MULTISELECTION IS INITIAL.
    MULTISEL = 1.
  ENDIF.

* verify the encoding flag
  IF NOT WITH_ENCODING IS INITIAL.
    BWITHENCODING = 1.
  ELSE.
    BWITHENCODING = 0.
  ENDIF.

* verify filefilter
  IF FILE_FILTER IS INITIAL.
    CONCATENATE FILETYPE_ALL
                FILETYPE_EXCEL
                FILETYPE_WORD
                FILETYPE_TEXT
                FILETYPE_HTML
                FILETYPE_RTF
                '|'
                INTO FILTER.
  ELSE.
    CONCATENATE FILE_FILTER '|' INTO FILTER.
  ENDIF.

  call method IS_SCRIPTING_ACTIVE receiving result = rt_value EXCEPTIONS others = 1.
  if rt_value = 1.

*   check the registry key
    call method cl_gui_frontend_services=>registry_get_dword_value
      exporting root = cl_gui_frontend_services=>HKEY_CURRENT_USER
                key = 'Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting'
                value = 'ShowNativeWinDlgs'
      importing reg_value = RCCU
      exceptions
        others = 1.

    call method cl_gui_frontend_services=>registry_get_dword_value
      exporting root = cl_gui_frontend_services=>HKEY_LOCAL_MACHINE
                key = 'Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting'
                value = 'ShowNativeWinDlgs'
      importing reg_value = RCLM
      exceptions
        others = 1.

    call method cl_gui_cfw=>flush.

    if ( RCCU = 0 or ( RCCU ne 1 and RCLM ne 1 ) ) and MULTISELECTION = space.

      RT_VALUE = 'X'.
      call FUNCTION 'GUI_FILE_LOAD_DIALOG'
        exporting
          WINDOW_TITLE      = WINDOW_TITLE
          DEFAULT_EXTENSION = DEFAULT_EXTENSION
          DEFAULT_FILE_NAME = DEFAULT_FILENAME
          WITH_ENCODING     = WITH_ENCODING
          INITIAL_DIRECTORY = INITIAL_DIRECTORY
          FILE_FILTER       = FILTER
        importing
          FULLPATH      = FULLPATH
          FILE_ENCODING = FILE_ENCODING
          USER_ACTION   = USER_ACTION.

      refresh file_table.
      if USER_ACTION = 0.
        RC = 1.
        filename = FULLPATH.
        append filename to FILE_TABLE.
        if WITH_ENCODING ne space.
          filename = FILE_ENCODING.
          append filename to FILE_TABLE.
        endif.
      else.
        RC = 0.
      endif.
      RET_VAL = 'X'.
    elseif ( RCCU = 0 or ( RCCU ne 1 and RCLM ne 1 ) ) and MULTISELECTION = 'X'.
      " evoke abap file open dialog with the multiple file selection option
      RT_VALUE = 'X'.
      refresh FILE_TABLE.

      " FULLPATH is the first file path
      " FILE_TABLE contains all file paths
      call FUNCTION 'GUI_MULTIPLE_FILE_LOAD_DIALOG'
        exporting
          WINDOW_TITLE      = WINDOW_TITLE
          DEFAULT_EXTENSION = DEFAULT_EXTENSION
          DEFAULT_FILE_NAME = DEFAULT_FILENAME
          WITH_ENCODING     = WITH_ENCODING
          INITIAL_DIRECTORY = INITIAL_DIRECTORY
          FILE_FILTER       = FILTER
        importing
          FULLPATH      = FULLPATH
          FILE_ENCODING = FILE_ENCODING
          USER_ACTION   = USER_ACTION
          FILE_TABLE    = FILE_TABLE.

      if USER_ACTION = 0.
        RC = 1.
        if WITH_ENCODING ne space.
          filename = FILE_ENCODING.
          append filename to FILE_TABLE.
        endif.
      else.
        " user_actopm = 9 -> file open dialog was canceled
        RC = 0.
      endif.
      RET_VAL = 'X'.
    endif.
  endif.

  if RT_VALUE ne 'X'.

   IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
    CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

    CALL FUNCTION 'ITS_FILE_OPEN_DIALOG'
      EXPORTING
        WINDOW_TITLE           = WINDOW_TITLE
        DEFAULT_EXTENSION      = DEFAULT_EXTENSION
        DEFAULT_FILENAME       = DEFAULT_FILENAME
        FILE_FILTER            = FILTER
        WITH_ENCODING          = WITH_ENCODING
        INITIAL_DIRECTORY      = INITIAL_DIRECTORY
        MULTISELECTION         = MULTISELECTION
      CHANGING
        FILE_TABLE             = FILE_TABLE
        RC                     = RC
      EXCEPTIONS
        OTHERS                 = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
    RET_VAL = 'X'.

   ELSE.

    CALL FUNCTION 'DP_STRETCH_SIMPLE_TABLE'
      EXPORTING
        copy_lines             = ' '
      IMPORTING
        stretched_data_ref     = table_ref
      TABLES
        data                   = FILE_TABLE
      EXCEPTIONS
        DP_ERROR_MULTIPLE_COLS = 1
        DP_ERROR_NOT_CHARLIKE  = 2.

    IF sy-subrc = 0.
      ASSIGN table_ref->* TO <table>.
    ELSE.
      ASSIGN FILE_TABLE TO <table>.
    ENDIF.

    CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
      EXPORTING
        H_CNTL                 = HANDLE->H_CONTROL
        MEDIUM                 = CNDP_MEDIUM_R3TABLE
        PROPERTYNAME           = 'R3TABLE'
      TABLES
        DATA                   = <table>
      EXCEPTIONS
        DP_ERROR_CREATE        = 1
        DP_ERROR_SEND_DATA     = 2
        DP_ERROR_ASSIGN        = 3
        DP_ERROR_INVALID_PARAM = 4
        DP_ERROR_TABNAME       = 5
        OTHERS                 = 6.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

*check if custom dialog is supported...........................
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
      EXPORTING
        COMPONENT            = 'sapinfocntl'
        FEATURE_NAME         = 'customdlg'
      RECEIVING
        RESULT               = RET_VAL
      EXCEPTIONS
        CNTL_ERROR           = 1
        ERROR_NO_GUI         = 2
        WRONG_PARAMETER      = 3
        NOT_SUPPORTED_BY_GUI = 4
        UNKNOWN_ERROR        = 5
        others               = 6.

    IF SY-SUBRC <> 0.
      RET_VAL = ABAP_FALSE.
    ENDIF.

*end custom dialog check support...............................

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
    CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

    IF NOT RET_VAL IS INITIAL.
      CALL METHOD HANDLE->CALL_METHOD
        EXPORTING
          METHOD     = 'FileOpenDialogEx'
          P_COUNT    = 7
          P1         = WINDOW_TITLE
          P2         = DEFAULT_EXTENSION
          P3         = DEFAULT_FILENAME
          P4         = FILTER
          P5         = INITIAL_DIRECTORY
          P6         = BWITHENCODING
          P7         = MULTISEL
          QUEUE_ONLY = ' '
        IMPORTING
          RESULT     = RC
        EXCEPTIONS
          OTHERS     = 1.

      IF SY-SUBRC <> 0.
        RAISE CNTL_ERROR.
      ENDIF.

    ELSE.
      CALL METHOD HANDLE->CALL_METHOD
        EXPORTING
          METHOD     = 'FileOpenDialog'
          P_COUNT    = 6
          P1         = WINDOW_TITLE
          P2         = DEFAULT_EXTENSION
          P3         = DEFAULT_FILENAME
          P4         = FILTER
          P5         = INITIAL_DIRECTORY
          P6         = MULTISEL
          QUEUE_ONLY = ' '
        IMPORTING
          RESULT     = RC
        EXCEPTIONS
          OTHERS     = 1.

      IF SY-SUBRC <> 0.
        RAISE CNTL_ERROR.
      ENDIF.
    ENDIF.

    CALL FUNCTION 'DP_CONTROL_GET_TABLE'
      EXPORTING
        H_CNTL                 = HANDLE->H_CONTROL
        PROPERTYNAME           = 'R3TABLE'
        MEDIUM                 = CNDP_MEDIUM_R3TABLE
      TABLES
        DATA                   = <table>
      EXCEPTIONS
        DP_ERROR_CREATE        = 1
        DP_ERROR_GET_PROPERTY  = 2
        DP_ERROR_GET_DATA      = 3
        DP_ERROR_INVALID_PARAM = 4
        OTHERS                 = 5.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    GET REFERENCE OF FILE_TABLE[] INTO orig_table_ref.

    IF orig_table_ref <> table_ref.
      FILE_TABLE = <table>[].
    ENDIF.
   ENDIF.
  ENDIF.

  IF RC = -1.
    RAISE FILE_OPEN_DIALOG_FAILED.
  ELSEIF RC < 1.
    USER_ACTION = ACTION_CANCEL.
  ELSE.
*the encoding is always the last entry in the file_table from...........
*the frontend...........................................................
*extract the encoding and delete the entry in file table................
*check if support bit is set............................................
    IF RET_VAL = 'X'.
      IF NOT WITH_ENCODING IS INITIAL.
        DESCRIBE TABLE FILE_TABLE LINES NO_ROWS.
        IF SY-SUBRC = 0.
          READ TABLE FILE_TABLE INTO L_RESULT INDEX NO_ROWS.
        ENDIF.

          CLEAR SY-SUBRC.
          FIELDLEN = STRLEN( L_RESULT ).
          IF NO_ROWS > 1.
            IF FIELDLEN > 0.
              FILE_ENCODING = L_RESULT(FIELDLEN).
              CASE FILE_ENCODING.
                WHEN 1.
                  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
                    CALL FUNCTION 'ITS_GET_UP_DOWN_CP'
                      EXPORTING
                        ENCODING       = '1'
                      CHANGING
                        FILE_ENCODING  = FILE_ENCODING
                      EXCEPTIONS
                        OTHERS         = 1.
                  ELSE.
                    DATA cp(4) TYPE C.
                    CALL 'CUR_LCL' id 'GUICP' field cp.
                    FILE_ENCODING  = cp.
                  ENDIF.
                WHEN 2.
                  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
                    CALL FUNCTION 'ITS_GET_UP_DOWN_CP'
                      EXPORTING
                        ENCODING       = '2'
                      CHANGING
                        FILE_ENCODING  = FILE_ENCODING
                      EXCEPTIONS
                        OTHERS         = 1.
                  ELSE.
                    CLEAR FILE_ENCODING .
                    DATA prcLoginLanguage TYPE T002-SPRAS.
                    CALL FUNCTION 'SCP_GET_LANGUAGE_ID'
                      IMPORTING
                        USER_LOGIN     = prcLoginLanguage
                      EXCEPTIONS
                        INTERNAL_ERROR = 1
                        OTHERS         = 2.
                    IF SY-SUBRC = 0.
                      DATA prc_cp TYPE  CPCODEPAGE.
                      CALL FUNCTION 'NLS_GET_FRONTEND_CP'
                        EXPORTING
                          LANGU                 = prcLoginLanguage
                          FETYPE                = 'MS'
                        IMPORTING
                          FRONTEND_CODEPAGE     = prc_cp
                        EXCEPTIONS
                          ILLEGAL_SYST_CODEPAGE = 1
                          NO_FRONTEND_CP_FOUND  = 2
                          INTERNAL_OR_DB_ERROR  = 3
                          OTHERS                = 4.
                      IF SY-SUBRC = 0.
                        MOVE prc_cp TO FILE_ENCODING .
                      ENDIF.
                    ENDIF.
                  ENDIF.
              ENDCASE.
*end........................................................
            ENDIF.
          ENDIF.
        DELETE FILE_TABLE INDEX NO_ROWS.
      ENDIF.
    ENDIF.
    USER_ACTION = ACTION_OK.
    if FILE_ENCODING = 0. clear FILE_ENCODING. ENDIF.
  ENDIF.


ENDMETHOD.                    "


METHOD FILE_SAVE_DIALOG .

*tita....
*local variables......................................................
  DATA: LEN TYPE I,
        PLATFORM_ID TYPE I,
        FILE_SEPARATOR TYPE C VALUE '\' ,
        FILTER TYPE STRING,
        ERROR_CODE TYPE N,
        ERR_CODE_C TYPE C,
        RCCU  TYPE I,
        RCLM  TYPE I.

  DATA: BWITHENCODING TYPE ABAP_BOOL,
        BPROMPT_ON_OVERWRITE TYPE ABAP_BOOL,
        RT_VALUE TYPE ABAP_BOOL,
        BPROMPT TYPE ABAP_BOOL.

  DATA : DL_PATH TYPE STRING,
         UPL_PATH TYPE STRING.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* Get the initial directory for download not set.......................
  IF INITIAL_DIRECTORY EQ SPACE.
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_UPLOAD_DOWNLOAD_PATH
      CHANGING
        UPLOAD_PATH                 = UPL_PATH
        DOWNLOAD_PATH               = DL_PATH
      EXCEPTIONS
        CNTL_ERROR                  = 1
        ERROR_NO_GUI                = 2
        NOT_SUPPORTED_BY_GUI        = 3
        GUI_UPLOAD_DOWNLOAD_PATH    = 4
        UPLOAD_DOWNLOAD_PATH_FAILED = 5
        others                      = 6.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
    IF DL_PATH IS NOT INITIAL.
      INITIAL_DIRECTORY = DL_PATH .
    ENDIF.
  ENDIF.

* end initial directory.................................................

* verify the encoding flag
  IF NOT WITH_ENCODING IS INITIAL.
    BWITHENCODING = 1.
  ELSE.
    BWITHENCODING = 0.
  ENDIF.

*set the overwrite flag.................................................

  IF NOT PROMPT_ON_OVERWRITE IS INITIAL.
    BPROMPT_ON_OVERWRITE = 1.
  ELSE.
    BPROMPT_ON_OVERWRITE = 0.
  ENDIF.

* verify the prompt on overwrite flag...................................

  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'overwriteonprompt'
    RECEIVING
      RESULT               = BPROMPT
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF SY-SUBRC <> 0.
    BPROMPT = ABAP_FALSE.
  ENDIF.


*verify filefilter......................................................
  IF FILE_FILTER IS INITIAL.
    CONCATENATE FILETYPE_ALL
                FILETYPE_EXCEL
                FILETYPE_WORD
                FILETYPE_TEXT
                FILETYPE_HTML
                FILETYPE_RTF
                '|'
                INTO FILTER.
  ELSE.
    CONCATENATE FILE_FILTER '|' INTO FILTER.
  ENDIF.

*do the call............................................................

 call method IS_SCRIPTING_ACTIVE receiving result = rt_value EXCEPTIONS others = 1.
 if rt_value = 1.

*   check the registry key
    call method cl_gui_frontend_services=>registry_get_dword_value
      exporting root = cl_gui_frontend_services=>HKEY_CURRENT_USER
                key = 'Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting'
                value = 'ShowNativeWinDlgs'
      importing reg_value = RCCU
      exceptions
        others = 1.

    call method cl_gui_frontend_services=>registry_get_dword_value
      exporting root = cl_gui_frontend_services=>HKEY_LOCAL_MACHINE
                key = 'Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting'
                value = 'ShowNativeWinDlgs'
      importing reg_value = RCLM
      exceptions
        others = 1.

    call method cl_gui_cfw=>flush.

    if RCCU = 0 or ( RCCU ne 1 and RCLM ne 1 ) .

      RT_VALUE = 'X'.
      call FUNCTION 'GUI_FILE_SAVE_DIALOG'
        exporting
          WINDOW_TITLE      = WINDOW_TITLE
          DEFAULT_EXTENSION = DEFAULT_EXTENSION
          DEFAULT_FILE_NAME = DEFAULT_FILE_NAME
          WITH_ENCODING     = WITH_ENCODING
          INITIAL_DIRECTORY = INITIAL_DIRECTORY
          FILE_FILTER       = FILTER
        importing
          FULLPATH      = FULLPATH
          FILE_ENCODING = FILE_ENCODING
          USER_ACTION   = USER_ACTION.
    endif.
 endif.

 if RT_VALUE ne 'X'.

  IF NOT BPROMPT IS INITIAL OR CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

    IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
      CALL FUNCTION 'ITS_FILE_SAVE_DIALOG'
        EXPORTING
          WINDOW_TITLE           = WINDOW_TITLE
          DEFAULT_EXTENSION      = DEFAULT_EXTENSION
          DEFAULT_FILENAME       = DEFAULT_FILE_NAME
          FILE_FILTER            = FILTER
          WITH_ENCODING          = WITH_ENCODING
          INITIAL_DIRECTORY      = INITIAL_DIRECTORY
          PROMPT_ON_OVERWRITE    = PROMPT_ON_OVERWRITE
        CHANGING
          FULLPATH               = FULLPATH
        EXCEPTIONS
          OTHERS                 = 1.
    ELSE.
      CALL METHOD HANDLE->CALL_METHOD
        EXPORTING
          METHOD     = 'FileSaveDialogEx'
          P_COUNT    = 7
          P1         = WINDOW_TITLE
          P2         = DEFAULT_EXTENSION
          P3         = DEFAULT_FILE_NAME
          P4         = FILTER
          P5         = INITIAL_DIRECTORY
          P6         = BWITHENCODING
          P7         = BPROMPT_ON_OVERWRITE
          QUEUE_ONLY = ' '
        IMPORTING
          RESULT     = FULLPATH
        EXCEPTIONS
          OTHERS     = 1.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
      CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

      CALL METHOD CL_GUI_CFW=>FLUSH
        EXCEPTIONS
          CNTL_SYSTEM_ERROR = 1
          CNTL_ERROR        = 2
          others            = 3.
    ENDIF.

*handle exceptions......................................................
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
    IF BWITHENCODING = 1.
      IF FULLPATH CS '?'.
        DATA ENCODING TYPE ABAP_ENCODING.
        SPLIT FULLPATH AT '?' INTO ENCODING FULLPATH.
        IF NOT ENCODING IS INITIAL.
           FILE_ENCODING = ENCODING.
        ENDIF.
      ENDIF.
    ENDIF.

  ELSE.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'FileSaveDialog'
        P_COUNT    = 5
        P1         = WINDOW_TITLE
        P2         = DEFAULT_EXTENSION
        P3         = DEFAULT_FILE_NAME
        P4         = FILTER
        P5         = INITIAL_DIRECTORY
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = FULLPATH
      EXCEPTIONS
        OTHERS     = 1.

* Incident 1004399 / 2015 / wrongfully accounted idle time for dialog transactions
    CALL FUNCTION 'PF_WRITE_STAT_ON_EOP'.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.

*handle exceptions......................................................
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.
* separate errorcode....................................................
  split FULLPATH at ';' INTO ERR_CODE_C FULLPATH.
  ERROR_CODE = ERR_CODE_C. " casting from type C to N to avoid dump.

 endif.

*check platform.........................................................
  CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_PLATFORM
    RECEIVING
      PLATFORM             = PLATFORM_ID
    EXCEPTIONS
      ERROR_NO_GUI         = 1
      CNTL_ERROR           = 2
      NOT_SUPPORTED_BY_GUI = 3
      others               = 4.
  IF SY-SUBRC <> 0.
    FILE_SEPARATOR = '\'.
    SY-SUBRC = 0.
  ELSE.

    IF PLATFORM_ID = PLATFORM_LINUX OR  PLATFORM_ID =  PLATFORM_MACOSX .
      FILE_SEPARATOR = '/'.
    ELSE.
      IF PLATFORM_ID = PLATFORM_NT50 OR PLATFORM_ID = PLATFORM_NT40.
        FILE_SEPARATOR = '\'.
      ENDIF.
    ENDIF.
  ENDIF.
*end check..............................................................
*check encoding and set the right value.................................
  CASE FILE_ENCODING.
    WHEN 1.
      IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
        CALL FUNCTION 'ITS_GET_UP_DOWN_CP'
          EXPORTING
            ENCODING       = '1'
          CHANGING
            FILE_ENCODING  = FILE_ENCODING
          EXCEPTIONS
            OTHERS         = 1.
      ELSE.
        DATA c_p(4) TYPE C.
        CALL 'CUR_LCL' id 'GUICP' field c_p.
        FILE_ENCODING  = c_p.
      ENDIF.
    WHEN 2.
      IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
        CALL FUNCTION 'ITS_GET_UP_DOWN_CP'
          EXPORTING
            ENCODING       = '2'
          CHANGING
            FILE_ENCODING  = FILE_ENCODING
          EXCEPTIONS
            OTHERS         = 1.
      ELSE.
        CLEAR FILE_ENCODING .
        DATA prcLoginLanguage TYPE T002-SPRAS.
        CALL FUNCTION 'SCP_GET_LANGUAGE_ID'
          IMPORTING
            USER_LOGIN     = prcLoginLanguage
          EXCEPTIONS
            INTERNAL_ERROR = 1
            OTHERS         = 2.
        IF SY-SUBRC = 0.
          DATA prc_cp TYPE  CPCODEPAGE.
          CALL FUNCTION 'NLS_GET_FRONTEND_CP'
            EXPORTING
              LANGU                 = prcLoginLanguage
              FETYPE                = 'MS'
            IMPORTING
              FRONTEND_CODEPAGE     = prc_cp
            EXCEPTIONS
              ILLEGAL_SYST_CODEPAGE = 1
              NO_FRONTEND_CP_FOUND  = 2
              INTERNAL_OR_DB_ERROR  = 3
              OTHERS                = 4.
          IF SY-SUBRC = 0.
            MOVE prc_cp TO FILE_ENCODING .
          ENDIF.
        ENDIF.
      ENDIF.
  ENDCASE.

  CASE ERROR_CODE.
    WHEN '0' OR 0.
* extract filename......................................................

      FILENAME = FULLPATH.

      WHILE SY-SUBRC = 0.
        SHIFT FILENAME UP TO FILE_SEPARATOR.
        IF SY-SUBRC = 0.
          SHIFT FILENAME.
        ENDIF.
      ENDWHILE.

* extract path..........................................................
      len = STRLEN( FILENAME ).
      LEN = LEN.
      PATH = FULLPATH.
      SHIFT PATH BY LEN PLACES RIGHT CIRCULAR.
      SHIFT PATH BY LEN PLACES LEFT.
      IF ERROR_CODE = '0' AND FILENAME = ''.
        USER_ACTION = ACTION_CANCEL.
      ELSE.
        USER_ACTION = ACTION_OK.
      ENDIF.
    WHEN '1'.
      MESSAGE 'INVALID_DEFAULT_FILE_NAME' TYPE 'I' RAISING INVALID_DEFAULT_FILE_NAME.
    WHEN '9'.
      USER_ACTION = ACTION_CANCEL.
  ENDCASE.
  if FILE_ENCODING = 0. clear FILE_ENCODING. endif.
ENDMETHOD.                    "


method FILE_SET_ATTRIBUTES .
*---------------------------------------------------------------------*
*       METHOD FILE_SET_ATTRIBUTES                                    *
*---------------------------------------------------------------------*
*       ........                                                      *
*---------------------------------------------------------------------*

  DATA: P_NORMAL TYPE I VALUE -1,
        P_READONLY TYPE I VALUE -1,
        P_HIDDEN TYPE I VALUE -1,
        P_ARCHIVE TYPE I VALUE -1.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF FILENAME IS INITIAL OR
     ( NORMAL IS NOT SUPPLIED   AND
       READONLY IS NOT supplied  AND
       HIDDEN IS NOT SUPPLIED   AND
       ARCHIVE IS NOT SUPPLIED ).

    RAISE WRONG_PARAMETER.
  ENDIF.

  IF NORMAL IS SUPPLIED.
    IF NORMAL IS NOT INITIAL.
      P_NORMAL = 1.
    ELSE.
      P_NORMAL = 0.
    ENDIF.
  ENDIF.

  IF READONLY IS SUPPLIED.
    IF READONLY IS NOT INITIAL.
      P_READONLY = 1.
    ELSE.
      P_READONLY = 0.
    ENDIF.
  ENDIF.

  IF HIDDEN IS SUPPLIED.
    IF HIDDEN IS NOT INITIAL.
      P_HIDDEN = 1.
    ELSE.
      P_HIDDEN = 0.
    ENDIF.
  ENDIF.

  IF ARCHIVE IS SUPPLIED.
    IF ARCHIVE IS NOT INITIAL.
      P_ARCHIVE = 1.
    ELSE.
      P_ARCHIVE = 0.
    ENDIF.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'SetFileAttribute'
      P1      = FILENAME
      P2      = P_NORMAL
      P3      = P_READONLY
      P4      = P_HIDDEN
      P5      = P_ARCHIVE
      P_COUNT = 5
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

endmethod.                    "FILE_SET_ATTRIBUTES


METHOD GET_COMPUTER_NAME.

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

  DATA: supported TYPE ABAP_BOOL.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.


  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'GET_COMPUTER_NAME'
    RECEIVING
      RESULT               = supported
    EXCEPTIONS
      CNTL_ERROR           = 1
      others               = 2.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF supported = abap_true.
    CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetComputerName'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = COMPUTER_NAME
    EXCEPTIONS
      OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "GET_COMPUTER_NAME


METHOD GET_DESKTOP_DIRECTORY.

* ...

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* check GUI
  IF JAVABEAN IS NOT INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetDesktopDirectory'
        P_COUNT = 0
      IMPORTING
        RESULT  = DESKTOP_DIRECTORY
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ELSE.
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_GET_CURRENT
      CHANGING
        CURRENT_DIRECTORY            = DESKTOP_DIRECTORY
      EXCEPTIONS
        DIRECTORY_GET_CURRENT_FAILED = 1
        CNTL_ERROR                   = 2
        ERROR_NO_GUI                 = 3
        NOT_SUPPORTED_BY_GUI         = 4
        others                       = 5.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "


METHOD GET_DRIVE_FREE_SPACE_MEGABYTE .
  data: len type i,
        flag type ABAP_BOOL,
        FREESPACE TYPE I.


*-check if valid GUI is available----------------------------------
  IF cl_gui_control=>www_active IS NOT INITIAL OR
     JAVABEAN IS NOT INITIAL.
    raise not_supported_by_gui.
  endif.

  IF cl_gui_control=>activex IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF DRIVE IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

* check for last \
  len = STRLEN( DRIVE ).
  LEN = LEN - 1.
  IF NOT DRIVE+len(1) = '\'.
    CONCATENATE DRIVE '\' INTO DRIVE.
  ENDIF.
CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
  EXPORTING
    COMPONENT            = 'sapinfocntl'
    FEATURE_NAME         = 'FreeSpaceinMB'
  RECEIVING
    RESULT               = flag
  EXCEPTIONS
    CNTL_ERROR           = 1
    others               = 2 .

IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
ENDIF.

  if flag = abap_true.

* do call to control
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetFreeSpaceForDriveEx'
        P1      = DRIVE
        P_COUNT = 1
      IMPORTING
        RESULT  = FREE_SPACE
      EXCEPTIONS
        OTHERS  = 1.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF .

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetFreeSpaceForDrive'
        P1      = DRIVE
        P_COUNT = 1
      IMPORTING
        RESULT  = FREESPACE
      EXCEPTIONS
        OTHERS  = 1.

    CALL METHOD CL_GUI_CFW=>FLUSH.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
    FREE_SPACE = FREESPACE DIV 1048576.
    CONCATENATE FREE_SPACE 'MB' INTO FREE_SPACE SEPARATED BY ' '.
  ENDIF.
ENDMETHOD.                    "GET_DRIVE_FREE_SPACE_MEGABYTE


METHOD GET_DRIVE_TYPE.

* call info control GetDriveType method

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF DRIVE IS INITIAL.
    RAISE BAD_PARAMETER.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetDriveType'
      P1         = DRIVE
      P_COUNT    = 1
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = DRIVE_TYPE
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "


  method GET_FEATURES_TAB.
    STATICS area_handle TYPE REF TO cl_gui_memory.
    DATA   memory_root TYPE REF TO cl_gui_memory_root.
    IF area_handle IS INITIAL.
      TRY.
          area_handle = cl_gui_memory=>attach_for_read( ).    "cl_gui_memory=>attach_for_read( ).
        CATCH cx_shm_attach_error.
          TRY.
*             try to set up the shared memory
              area_handle = cl_gui_memory=>attach_for_write( ).
              CREATE OBJECT memory_root AREA HANDLE area_handle.
              area_handle->set_root( memory_root ).
*             Raising unknown_error exception for error reading features, since we cannot add a new exception type
              memory_root->set_features_tab( exceptions UNKNOWN_ERROR = 1 ).
              if sy-subrc ne 0.
                 area_handle->detach_rollback( ).
                 clear area_handle.
*                Raising unknown_error exception for error reading features, since we cannot add a new exception type
                 RAISE UNKNOWN_ERROR.
              endif.
              area_handle->detach_commit( ).
*
              area_handle = cl_gui_memory=>attach_for_read( ).
            CATCH cx_shm_attach_error
                  cx_shm_out_of_memory.
              clear area_handle.
              CREATE OBJECT memory_root.
              memory_root->set_features_tab( ).
          ENDTRY.
      ENDTRY.
    ENDIF.

    DATA: features_line type cl_gui_memory_root=>sfes_features_record_type_root.
    DATA features_wa type sfes_features_record_type.

    IF area_handle is NOT INITIAL.

      loop at area_handle->root->features_tab into features_line.

         features_wa-featurename = features_line-featurename.
         features_wa-value = features_line-value.
         features_wa-component = features_line-component.

         APPEND features_wa TO features_tab.

      endloop.

    ELSEIF memory_root IS NOT INITIAL.

      loop at  memory_root->features_tab into features_line.

        features_wa-featurename = features_line-featurename.
        features_wa-value = features_line-value.
        features_wa-component = features_line-component.

        APPEND features_wa TO features_tab.

      endloop.

    ELSE.
*     Raising unknown_error exception for error reading features, since we cannot add a new exception type
      RAISE UNKNOWN_ERROR.
    ENDIF.

  endmethod.


method GET_FILE_SEPARATOR.
  DATA: P_SEPARATOR_WINDOWS TYPE C VALUE '\',
        P_SEPARATOR_UNIX    TYPE C VALUE '/',
        P_SEPARATOR_JAV     TYPE C ,
        PLATFORM_ID TYPE I.

  CLASS CL_GUI_CONTROL DEFINITION LOAD.

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR IS INITIAL.
* SAPGUI for HTML
    IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

      CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_PLATFORM
        RECEIVING
          PLATFORM             = PLATFORM_ID
        EXCEPTIONS
          ERROR_NO_GUI         = 1
          CNTL_ERROR           = 2
          NOT_SUPPORTED_BY_GUI = 3
          others               = 4.
      IF SY-SUBRC <> 0.
        RAISE CNTL_ERROR.
      ENDIF.

      IF PLATFORM_ID = CL_GUI_FRONTEND_SERVICES=>PLATFORM_WINDOWSXP.
        MOVE P_SEPARATOR_WINDOWS TO CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
      ELSEIF PLATFORM_ID = CL_GUI_FRONTEND_SERVICES=>PLATFORM_LINUX.
        MOVE P_SEPARATOR_UNIX TO CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
      ELSEIF PLATFORM_ID = CL_GUI_FRONTEND_SERVICES=>PLATFORM_MACOSX.
        MOVE P_SEPARATOR_UNIX TO CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
      ELSE.
        RAISE NOT_SUPPORTED_BY_GUI.
      ENDIF.
    ENDIF.
*end SAPGUI for HTML

* SAPGUI for Java
    IF CL_GUI_CONTROL=>JAVABEAN IS NOT INITIAL.
      CALL METHOD HANDLE->CALL_METHOD
        EXPORTING
          METHOD  = 'getFileSeparator'
          P_COUNT = 0
        IMPORTING
          RESULT  = P_SEPARATOR_JAV
        EXCEPTIONS
          OTHERS  = 1.

      CALL METHOD CL_GUI_CFW=>FLUSH
        EXCEPTIONS
          CNTL_SYSTEM_ERROR = 1
          CNTL_ERROR        = 2
          others            = 3.

      IF SY-SUBRC <> 0.
*      check platform.........................................................
        CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_PLATFORM
          RECEIVING
            PLATFORM             = PLATFORM_ID
          EXCEPTIONS
            ERROR_NO_GUI         = 1
            CNTL_ERROR           = 2
            NOT_SUPPORTED_BY_GUI = 3
            others               = 4.
        IF SY-SUBRC <> 0.
          P_SEPARATOR_JAV = '\'.
        ENDIF.

        IF PLATFORM_ID = PLATFORM_MAC.
          P_SEPARATOR_JAV = ':'.
        ELSE.
          IF PLATFORM_ID = PLATFORM_NT50 OR PLATFORM_ID = PLATFORM_NT40 OR PLATFORM_ID = PLATFORM_OS2 OR PLATFORM_ID = PLATFORM_WINDOWSXP.
            P_SEPARATOR_JAV = '\'.
          ELSE.
            P_SEPARATOR_JAV = '/'.
          ENDIF.
        ENDIF.
*      end check..............................................................
      ENDIF.
      MOVE P_SEPARATOR_JAV TO CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
    ENDIF.
*end Java GUI

*win32 GUI
    IF CL_GUI_CONTROL=>ACTIVEX IS NOT INITIAL AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL..
      MOVE P_SEPARATOR_WINDOWS TO CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
    ENDIF.
  ENDIF.

  FILE_SEPARATOR = CL_GUI_FRONTEND_SERVICES=>FILE_SEPARATOR.
endmethod.                    "GET_FILE_SEPARATOR


METHOD GET_FREE_SPACE_FOR_DRIVE .

* ...

  data: len type i.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* check parameter
  IF DRIVE IS INITIAL.
    RAISE WRONG_PARAMETER.
  ENDIF.

* check for last \
  len = STRLEN( DRIVE ).
  LEN = LEN - 1.
  IF NOT DRIVE+len(1) = '\'.
    CONCATENATE DRIVE '\' INTO DRIVE.
  ENDIF.

* do call to control
  CALL METHOD HANDLE->CALL_METHOD
  EXPORTING
    METHOD  = 'GetFreeSpaceForDrive'
    P1      = DRIVE
    P_COUNT = 1
  IMPORTING
    RESULT = FREE_SPACE
  EXCEPTIONS
    OTHERS = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.


METHOD get_free_space_for_drive_long .

* ...

  DATA: len TYPE i.
  DATA: ret_val                  TYPE abap_bool,
        frontend_method_name(42) VALUE 'GetFreeSpaceForDriveLong'.

* check class constructor error code
  IF is_valid_handle( ) NE 0.
    RAISE cntl_error.
  ENDIF.

* check parameter
  IF drive IS INITIAL.
    RAISE wrong_parameter.
  ENDIF.

* check for last \
  len = strlen( drive ).
  len = len - 1.
  IF NOT drive+len(1) = '\'.
    CONCATENATE drive '\' INTO drive.
  ENDIF.

*check if the method is supported by the windows gui
  CALL METHOD cl_gui_frontend_services=>check_gui_support
    EXPORTING
      component            = 'sapinfocntl'
      feature_name         = 'GET_FREE_SPACE_FOR_DRIVE_LONG'
    RECEIVING
      result               = ret_val
    EXCEPTIONS
      cntl_error           = 1
      error_no_gui         = 2
      wrong_parameter      = 3
      not_supported_by_gui = 4
      unknown_error        = 5
      OTHERS               = 6.

  IF sy-subrc <> 0.
    ret_val = abap_false.
  ENDIF.

*use older c++ method if the new one is not supported by windows gui
  IF ret_val IS INITIAL.
    frontend_method_name = 'GetFreeSpaceForDrive'.
  ENDIF.

* do call to control
  CALL METHOD handle->call_method
    EXPORTING
      method  = frontend_method_name
      p1      = drive
      p_count = 1
    IMPORTING
      result  = free_space
    EXCEPTIONS
      OTHERS  = 1.

  IF sy-subrc <> 0.
    RAISE cntl_error.
  ENDIF.

ENDMETHOD.


method GET_GUI_PROPERTIES .

  type-pools: ixml.
  class cl_ixml definition load.
  CLASS CL_GUI_CONTROL DEFINITION LOAD .

  data val type string.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.

* special handling for SAPGUI for HTML
  IF cl_gui_control=>www_active IS NOT INITIAL.
    CALL FUNCTION 'ITS_GET_GUI_PROPERTIES'
      CHANGING
        STREAM                     = STREAM
     EXCEPTIONS
       NOT_SUPPORTED_BY_GUI       = 1
       OTHERS                     = 2
            .
    CASE SY-SUBRC.
      WHEN 0.
      WHEN 1.
        RAISE NOT_SUPPORTED_BY_GUI.
      WHEN OTHERS.
        RAISE CNTL_ERROR.
    ENDCASE.
    EXIT.
  ENDIF.


* do call to control
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD = 'GetGuiFeatures'
    IMPORTING
      RESULT = STREAM
    EXCEPTIONS
      OTHERS = 1.
  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

*  val = STREAM.
*
*
*-- create the main factory
*data: pixml type ref to if_ixml.
*pixml = cl_ixml=>create( ).
*
*-- create the initial document
*data: pdocument type ref to if_ixml_document.
*pdocument = pixml->create_document( ).
*
*-- create the stream factory
*data: pstreamfactory type ref to if_ixml_stream_factory.
*pstreamfactory = pixml->create_stream_factory( ).
*
*-- create a stream for the input (string)
*data: pistream type ref to if_ixml_istream.
*data: xml_doc type string value 'hello world!'.
*
*pistream = pstreamfactory->create_istream_string( val ).
*
*
*-- create the parser
*data: pparser type ref to if_ixml_parser.
*pparser = pixml->create_parser( stream_factory  = pstreamfactory
*                                  istream       = pistream
*                                  document      = pdocument ).
*-- parse the stream
*if pparser->parse( ) ne 0.
*  if pparser->num_errors( ) ne 0.
*    data: count type i.
*    count = pparser->num_errors( ).
*    write: count, ' parse errors have occured:'.    "#EC NOTEXT
*    data: pparseerror type ref to if_ixml_parse_error,
*          i type i.
*    data: index type i value 0.
*      while index < count.
*        pparseerror = pparser->get_error( index = index ).
*        i = pparseerror->get_line( ).
*        write: 'line: ', i.                         "#EC NOTEXT
*        i = pparseerror->get_column( ).
*        write: 'column: ', i.                       "#EC NOTEXT
*        data: string type string.
*        string = pparseerror->get_reason( ).
*        write: string.
*        index = index + 1.
*      endwhile.
*  endif.
*endif.
*
*data: iterator type ref to if_ixml_node_iterator,
*      node     type ref to if_ixml_node.
*data node type ref to if_ixml_node.
*data str1 type string.
*
*
*data: filter type ref to if_ixml_node_filter.
*filter = pdocument->create_filter_name( name = 'name' ).
*data: iterator type ref to if_ixml_node_iterator.
*iterator = pdocument->create_iterator_filtered( filter ).
*
*iterator = pdocument->create_iterator( ).
*node = iterator->get_next( ).
*while not node is initial.
*str1 = node->get_value( ).
*write: str1.
*  node = iterator->get_next( ).
*endwhile.

endmethod.                    "GET_GUI_PROPERTIES


method GET_GUI_VERSION.


DATA: L_RESULT TYPE FILE_TABLE,
      RET_CODE TYPE I.

  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

 CLASS CL_GUI_CONTROL DEFINITION LOAD .

*assign dp table to control..........................
     CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
      EXPORTING
        H_CNTL                 = HANDLE->H_CONTROL
        MEDIUM                 = CNDP_MEDIUM_R3TABLE
        PROPERTYNAME           = 'R3TABLE'
      TABLES
        DATA                   = VERSION_TABLE
      EXCEPTIONS
        DP_ERROR_CREATE        = 1
        DP_ERROR_SEND_DATA     = 2
        DP_ERROR_ASSIGN        = 3
        DP_ERROR_INVALID_PARAM = 4
        DP_ERROR_TABNAME       = 5
        OTHERS                 = 6.

    IF SY-SUBRC <> 0.
      RAISE CANT_WRITE_VERSION_TABLE.
    ENDIF.

*call the method......................................
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetGuiVersion'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = RC
    EXCEPTIONS
      OTHERS     = 1.


  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0.
    RAISE GET_GUI_VERSION_FAILED.
  ENDIF.


*end call.............................................

    CALL FUNCTION 'DP_CONTROL_GET_TABLE'
      EXPORTING
        H_CNTL                 = HANDLE->H_CONTROL
        PROPERTYNAME           = 'R3TABLE'
        MEDIUM                 = CNDP_MEDIUM_R3TABLE
      TABLES
        DATA                   = VERSION_TABLE
      EXCEPTIONS
        DP_ERROR_CREATE        = 1
        DP_ERROR_GET_PROPERTY  = 2
        DP_ERROR_GET_DATA      = 3
        DP_ERROR_INVALID_PARAM = 4
        OTHERS                 = 5.

    IF SY-SUBRC <> 0.
      RAISE CANT_WRITE_VERSION_TABLE.
    ENDIF.
  IF RC <> 0.
    RAISE GET_GUI_VERSION_FAILED.
  ENDIF.

endmethod.


method GET_IP_ADDRESS .

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetIPAddress'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = IP_ADDRESS
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.
  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

endmethod.                    "


method GET_LF_FOR_DESTINATION_GUI .

  DATA: PLATFORM_ID TYPE I.

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* platform verification............................................
  IF GUI_CRLF IS INITIAL.

    CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_PLATFORM
      RECEIVING
        PLATFORM             = PLATFORM_ID
      EXCEPTIONS
        ERROR_NO_GUI         = 1
        CNTL_ERROR           = 2
        NOT_SUPPORTED_BY_GUI = 3
        others               = 4.

    IF SY-SUBRC <> 0.
      PLATFORM_ID = CL_GUI_FRONTEND_SERVICES=>PLATFORM_UNKNOWN .
    ENDIF.

    CASE PLATFORM_ID.
      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_WINDOWSXP.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_NT50.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_NT40.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_NT351.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_WINDOWS95.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_WINDOWS98.
        MOVE CL_ABAP_CHAR_UTILITIES=>CR_LF TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_MAC.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_MACOSX.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_AIX.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_HPUX.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_LINUX.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_SOLARIS.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_TRU64.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_OS2.
        MOVE CL_ABAP_CHAR_UTILITIES=>NEWLINE TO GUI_CRLF.

      WHEN CL_GUI_FRONTEND_SERVICES=>PLATFORM_UNKNOWN.
        RAISE CNTL_ERROR.
    ENDCASE.
  ENDIF.

  MOVE GUI_CRLF TO LINEFEED.
endmethod.


method GET_PLATFORM.
*---------------------------------------------------------------------*
*       METHOD GET_PLATFORM                                           *
*---------------------------------------------------------------------*
*       ........                                                      *
*---------------------------------------------------------------------*
* ...
  data: minorversion type i,
        majorversion type i,
        platformID type i,
        version(10) type C,
        USER_AGENT TYPE TABLE of char255,
        USER_AGENT_WA TYPE CHAR255,
        bPLATFORMEX   TYPE ABAP_BOOL.

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* only determine platform once
  IF M_PLATFORM IS INITIAL.

*   SAPGUI for HTML
    IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.

      " read User agent from the ITS context and extract
      " the OS platform.
      CALL FUNCTION 'ALEWEB_GET_CONTEXT'
        EXPORTING
          FIELDNAME             = '~HTTP_USER_AGENT'
          FIELDINDEX            = 1
        TABLES
          DATA_TAB              = USER_AGENT
        EXCEPTIONS
          INVALID_INDEX         = 1
          SYSTEM_FAILURE        = 2
          ITS_NOT_AVAILABLE     = 3
          COMMUNICATION_FAILURE = 4
          OTHERS                = 5.

      IF SY-SUBRC <> 0.
        RAISE CNTL_ERROR.
      ENDIF.

      READ TABLE USER_AGENT INTO USER_AGENT_WA INDEX 1.

      IF USER_AGENT_WA CS 'Windows'.    "#EC NOTEXT
        M_PLATFORM = CL_GUI_FRONTEND_SERVICES=>PLATFORM_WINDOWSXP.
      ELSEIF USER_AGENT_WA CS 'Linux'.  "#EC NOTEXT
        M_PLATFORM = CL_GUI_FRONTEND_SERVICES=>PLATFORM_LINUX.
      ELSEIF USER_AGENT_WA CS 'CrOS'.  "#EC NOTEXT
        M_PLATFORM = CL_GUI_FRONTEND_SERVICES=>PLATFORM_LINUX.
      ELSEIF USER_AGENT_WA CS 'Mac'.    "#EC NOTEXT
        M_PLATFORM = CL_GUI_FRONTEND_SERVICES=>PLATFORM_MACOSX.
      ELSE.
        M_PLATFORM = CL_GUI_FRONTEND_SERVICES=>PLATFORM_UNKNOWN.
      ENDIF.

    ELSE.

* check if extended version is supported, valid for java and windows gui
      CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
        EXPORTING
          COMPONENT            = 'sapinfocntl'
          FEATURE_NAME         = 'platformex'
        RECEIVING
          RESULT               = bPLATFORMEX
        EXCEPTIONS
          CNTL_ERROR           = 1
          ERROR_NO_GUI         = 2
          WRONG_PARAMETER      = 3
          NOT_SUPPORTED_BY_GUI = 4
          UNKNOWN_ERROR        = 5
          others               = 6.

      CALL METHOD CL_GUI_CFW=>FLUSH.
      IF SY-SUBRC <> 0.
        bPLATFORMEX = ABAP_FALSE.
      ENDIF.

      IF bPLATFORMEX = ABAP_TRUE.

        CALL METHOD HANDLE->CALL_METHOD
          EXPORTING
            METHOD     = 'GetPlatformEx'
            P_COUNT    = 0
            QUEUE_ONLY = ' '
          IMPORTING
            RESULT     = PLATFORMID
          EXCEPTIONS
            OTHERS     = 1.

        CALL METHOD CL_GUI_CFW=>FLUSH
          EXCEPTIONS
            CNTL_SYSTEM_ERROR = 1
            CNTL_ERROR        = 2
            others            = 3.

        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.

        MOVE PLATFORMID TO M_PLATFORM.
      ELSE.
*     SAP GUI for Windows
        IF ACTIVEX IS NOT INITIAL.

* returns Windows Platform
*
* VER_PLATFORM_WIN32s             0
* VER_PLATFORM_WIN32_WINDOWS      1       (Win95/98)
* VER_PLATFORM_WIN32_NT           2

        CALL METHOD HANDLE->CALL_METHOD
          EXPORTING
            METHOD     = 'GetWindowsPlatform'
            P_COUNT    = 0
            QUEUE_ONLY = ' '
          IMPORTING
            RESULT     = platformID
          EXCEPTIONS
            OTHERS     = 1.

        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.

* returns windows version dwMajorVersion.dwMinorVersion
*
*dwMajorVersion
*Identifies the major version number of the operating system. For
*example, for Windows NT version 3.51, the major version number is 3;
*and for Windows NT version 4.0, the major version number is 4.
*
*dwMinorVersion
*Identifies the minor version number of the operating system. For
*example, for Windows NT version 3.51, the minor version number is 51;
*and for Windows NT version 4.0, the minor version number is 0.
*
*For Windows 95, dwMinorVersion is zero.
*
*For Windows 98, dwMinorVersion is greater than zero.

        CALL METHOD HANDLE->CALL_METHOD
          EXPORTING
            METHOD     = 'GetWindowsVersion'
            P_COUNT    = 0
            QUEUE_ONLY = ' '
          IMPORTING
            RESULT     = VERSION
          EXCEPTIONS
            OTHERS     = 1.

        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.

        CALL METHOD CL_GUI_CFW=>FLUSH
          EXCEPTIONS
            CNTL_SYSTEM_ERROR = 1
            CNTL_ERROR        = 2
            others            = 3.
        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.


* parse platform information

        IF PLATFORMID = 0.                                  " WIN32S
          M_PLATFORM = PLATFORM_UNKNOWN.
        ELSEIF PLATFORMID = 1.             " WIN32_WINDOWS
          MOVE VERSION+2(1) TO minorversion.
          IF minorversion = 0.
            M_PLATFORM = PLATFORM_WINDOWS95.
          ELSEIF minorversion > 0.
            M_PLATFORM = PLATFORM_WINDOWS98.
          ELSE.
            M_PLATFORM = PLATFORM_UNKNOWN.
          ENDIF.
        ELSEIF PLATFORMID = 2.                              " WIN32_NT
          MOVE VERSION(1) TO majorversion.
          IF majorversion = 3.
            M_PLATFORM = PLATFORM_NT351.
          ELSEIF majorversion = 4.
            M_PLATFORM = PLATFORM_NT40.
          ELSEIF majorversion = 5.
            MOVE VERSION+2(1) TO minorversion.
              IF minorversion = 0.
                M_PLATFORM = PLATFORM_NT50.
              ELSE.
                M_PLATFORM = PLATFORM_WINDOWSXP.
            ENDIF.
          ELSE.
            M_PLATFORM = PLATFORM_UNKNOWN.
          ENDIF.
        ELSE.
          M_PLATFORM = PLATFORM_UNKNOWN.
        ENDIF.
* JAVA platform
      ELSEIF JAVABEAN IS NOT INITIAL.

        CALL METHOD HANDLE->CALL_METHOD
          EXPORTING
            METHOD     = 'GetWindowsPlatform'
            P_COUNT    = 0
            QUEUE_ONLY = ' '
          IMPORTING
            RESULT     = platformID
          EXCEPTIONS
            OTHERS     = 1.

        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.

        CALL METHOD CL_GUI_CFW=>FLUSH
          EXCEPTIONS
            CNTL_SYSTEM_ERROR = 1
            CNTL_ERROR        = 2
            others            = 3.
        IF SY-SUBRC <> 0.
          RAISE CNTL_ERROR.
        ENDIF.

* platform parsing JAVA
*public static final int OS_OTHERS  = 0;
*public static final int OS_MAC	  = 1;
*public static final int OS_WINNT   = 2;
*public static final int OS_WIN95   = 3;
*public static final int OS_WIN98   = 4;
*public static final int OS_WIN2000 = 5;
*public static final int OS_OS2	  = 6;
*public static final int OS_LINUX   = 7;
*public static final int OS_HPUX    = 8;
*public static final int OS_TRU64   = 9;
*public static final int OS_AIX     = 10;
*public static final int OS_SOLARIS = 11;
*public static final int OS_MACOSX  = 12;

        case platformID.
          WHEN 0.
            M_PLATFORM = PLATFORM_UNKNOWN.
          WHEN 1.
            M_PLATFORM = PLATFORM_MAC.
          WHEN 2.
            M_PLATFORM = PLATFORM_NT40.
          WHEN 3.
            M_PLATFORM = PLATFORM_WINDOWS95.
          WHEN 4.
            M_PLATFORM = PLATFORM_WINDOWS98.
          WHEN 5.
            M_PLATFORM = PLATFORM_NT50.
          WHEN 6.
            M_PLATFORM = PLATFORM_OS2.
          WHEN 7.
            M_PLATFORM = PLATFORM_LINUX.
          WHEN 8.
            M_PLATFORM = PLATFORM_HPUX.
          WHEN 9.
            M_PLATFORM = PLATFORM_TRU64.
          WHEN 10.
            M_PLATFORM = PLATFORM_AIX.
          WHEN 11.
            M_PLATFORM = PLATFORM_SOLARIS.
          WHEN 12.
            M_PLATFORM = PLATFORM_MACOSX.
          WHEN 13.
            M_PLATFORM = PLATFORM_WINDOWSXP.
          WHEN OTHERS.
            M_PLATFORM = PLATFORM_UNKNOWN.
        ENDCASE.
        ENDIF.
      ENDIF.
    ENDIF.
  ENDIF.

  PLATFORM = M_PLATFORM.

endmethod.                    "GET_PLATFORM


method GET_SAPGUI_DIRECTORY.
* ...

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  if www_active is initial.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD     = 'GetProgramPath'
        P_COUNT    = 0
        QUEUE_ONLY = ' '
      IMPORTING
        RESULT     = SAPGUI_DIRECTORY
      EXCEPTIONS
        OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  else.
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_GET_CURRENT
      CHANGING
        CURRENT_DIRECTORY            = SAPGUI_DIRECTORY
      EXCEPTIONS
        DIRECTORY_GET_CURRENT_FAILED = 1
        CNTL_ERROR                   = 2
        ERROR_NO_GUI                 = 3
        NOT_SUPPORTED_BY_GUI         = 4
        others                       = 5.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  endif.

endmethod.                    "GET_SAPGUI_DIRECTORY


method GET_SAPGUI_WORKDIR .

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF WWW_ACTIVE IS INITIAL.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD = 'GetSapWorkDir'
      IMPORTING
        RESULT = SAPWORKDIR
      EXCEPTIONS
        OTHERS = 1.
    CALL METHOD CL_GUI_CFW=>FLUSH.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

  IF SAPWORKDIR IS INITIAL.
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_GET_CURRENT
      CHANGING
        CURRENT_DIRECTORY            = SAPWORKDIR
      EXCEPTIONS
        DIRECTORY_GET_CURRENT_FAILED = 1
        CNTL_ERROR                   = 2
        ERROR_NO_GUI                 = 3
        NOT_SUPPORTED_BY_GUI         = 4
        others                       = 5.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

endmethod.                    "GET_SAPGUI_WORKDIR


method GET_SAPLOGON_ENCODING.
*tita.............

  DATA: IS_SUPPORTED TYPE ABAP_BOOL,
        ERROR_CODE TYPE N.

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

*-check if valid GUI is available----------------------------------
  IF WWW_ACTIVE IS NOT INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF IS_VALID_HANDLE( ) NE 0.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* check gui support....................................................
  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'saplogoncodepage'
    RECEIVING
      RESULT               = IS_SUPPORTED
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF SY-SUBRC <> 0.
    IS_SUPPORTED = ABAP_FALSE.
  ENDIF.

  IF IS_SUPPORTED IS NOT INITIAL.
    IF SAPLOGON_ENCODING IS INITIAL.

* call the controlmanager method GetSapLogonCodepage...................
      CALL METHOD OF H_GUI 'GetSapLogonCodepage' = FILE_ENCODING.

      IF SY-SUBRC <> 0.
        RAISE CNTL_ERROR.
      ENDIF.

*......................................................................

      IF FILE_ENCODING CS ';'.
        split FILE_ENCODING at ';' INTO ERROR_CODE FILE_ENCODING.
      ENDIF.
* Encoding 2: Get the Non-Unicode codepage for the login language
      CASE FILE_ENCODING.
        WHEN 0 OR 1.

          DATA cp(4) TYPE C.
          CALL 'CUR_LCL' id 'GUICP' field cp.
          SAPLOGON_ENCODING  = cp.

        WHEN 2.
          CLEAR FILE_ENCODING .
          DATA prcLoginLanguage TYPE T002-SPRAS.
          CALL FUNCTION 'SCP_GET_LANGUAGE_ID'
            IMPORTING
              USER_LOGIN     = prcLoginLanguage
            EXCEPTIONS
              INTERNAL_ERROR = 1
              OTHERS         = 2.
          IF SY-SUBRC = 0.
            DATA prc_cp TYPE  CPCODEPAGE.
            CALL FUNCTION 'NLS_GET_FRONTEND_CP'
              EXPORTING
                LANGU                 = prcLoginLanguage
                FETYPE                = 'MS'
              IMPORTING
                FRONTEND_CODEPAGE     = prc_cp
              EXCEPTIONS
                ILLEGAL_SYST_CODEPAGE = 1
                NO_FRONTEND_CP_FOUND  = 2
                INTERNAL_OR_DB_ERROR  = 3
                OTHERS                = 4.
            IF SY-SUBRC = 0.
              MOVE prc_cp TO SAPLOGON_ENCODING .
            ENDIF.
          ENDIF.
        WHEN OTHERS.
          MOVE FILE_ENCODING TO SAPLOGON_ENCODING.
      ENDCASE.
* Encoding 1 or still not found: Use SAP GUI encoding.
    ENDIF.
ELSE.
  RAISE NOT_SUPPORTED_BY_GUI.
ENDIF.

MOVE SAPLOGON_ENCODING TO FILE_ENCODING.
endmethod.                    "GET_SAPLOGON_ENCODING


method GET_SCREENSHOT.
  "-type declarations---------------------------------------------------
  TYPES: t_table_line(256) TYPE X,
         t_image_table_line TYPE STANDARD TABLE OF t_table_line.

  "-variables-----------------------------------------------------------
  DATA: feature_supported_b TYPE ABAP_BOOL,
        gui_available_b TYPE CHAR1,
        image_size_i TYPE I,
        image_size_str TYPE STRING,
        image_table TYPE t_image_table_line,
        result_str TYPE STRING,
        rc_str TYPE STRING,
        table_line TYPE t_table_line.

  "-initial checks------------------------------------------------------
  CALL FUNCTION 'GUI_IS_AVAILABLE'     " check if running in batch, etc.
    IMPORTING
      return = gui_available_b.

  IF gui_available_b IS INITIAL.
    RAISE ERROR_NO_GUI.
  ENDIF.

  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING                          " check GUI screenshot support
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'GET_SCREENSHOT'
    RECEIVING
      RESULT               = feature_supported_b
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF ( SY-SUBRC <> 0 ) OR ( feature_supported_b = ABAP_FALSE ).
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  "-initialization------------------------------------------------------
  CLEAR mime_type_str.
  CLEAR image.

  "-send data table to frontend-----------------------------------------
  CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
      PROPERTYNAME           = 'R3TABLE'
    TABLES
      DATA                   = image_table
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_SEND_DATA     = 2
      DP_ERROR_ASSIGN        = 3
      DP_ERROR_INVALID_PARAM = 4
      DP_ERROR_TABNAME       = 5
      OTHERS                 = 6.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  "-create screenshot of topmost modal----------------------------------
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'CreateScreenshot'
    IMPORTING
      RESULT     = result_str
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  SPLIT result_str AT ';' INTO rc_str image_size_str mime_type_str.

  image_size_i = image_size_str.

  CASE rc_str.
    WHEN '0'.

    WHEN '1'.
      RAISE ACCESS_DENIED.
    WHEN OTHERS.
      RAISE CNTL_ERROR.
  ENDCASE.

  "-retrieve image data from frontend-----------------------------------
  CALL FUNCTION 'DP_CONTROL_GET_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      PROPERTYNAME           = 'R3TABLE'
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
    TABLES
      DATA                   = image_table
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_GET_PROPERTY  = 2
      DP_ERROR_GET_DATA      = 3
      DP_ERROR_INVALID_PARAM = 4
      OTHERS                 = 5.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  LOOP AT image_table INTO table_line.
    IF image_size_i > 256.
      image = image && table_line.

      image_size_i = image_size_i - 256.
    ELSE.
      image = image && table_line+0(image_size_i).

      image_size_i = 0.
    ENDIF.
  ENDLOOP.

endmethod.


METHOD GET_SYSTEM_DIRECTORY.

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
       METHOD  = 'GetSystemDirectory'
       P_COUNT = 0
       QUEUE_ONLY = ' '
    IMPORTING
       RESULT = SYSTEM_DIRECTORY
    EXCEPTIONS
       OTHERS = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.


method GET_TEMP_DIRECTORY .

* ...

*-check if valid GUI is available----------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

  IF www_active IS INITIAL.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetTempPath'
        P_COUNT = 0
      IMPORTING
        RESULT  = TEMP_DIR
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.
    CALL FUNCTION 'ITS_GET_TEMP_DIRECTORY'
      CHANGING
        TEMP_DIR = TEMP_DIR
      EXCEPTIONS
        OTHERS        = 1.
    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "


method GET_UPLOAD_DOWNLOAD_PATH.

  data : DOWNL_PATH(300) type C,
         UPL_PATH(300) type C,
         FILE_SEPARATOR TYPE C,
         LAST_CHAR TYPE C,
         LAST_CHAR_POS TYPE I,
         CURRENT_DIR TYPE STRING VALUE '',
         DL_PATH TYPE STRING,
         UL_PATH TYPE STRING.

*-check if valid GUI is available---------------------------------------
  IF IS_VALID_HANDLE( ) NE 0 AND cl_gui_control=>www_active IS INITIAL.
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

*-Obtain file separator character---------------------------------------
  CALL METHOD CL_GUI_FRONTEND_SERVICES=>GET_FILE_SEPARATOR
    CHANGING
      file_separator        = FILE_SEPARATOR
    EXCEPTIONS
      cntl_error            = 1
      error_no_gui          = 2
      not_supported_by_gui  = 3
      others                = 4.

  IF SY-SUBRC <> 0.
    FILE_SEPARATOR = ''.
  ENDIF.

*-Download path---------------------------------------------------------
  GET PARAMETER ID 'GR8' FIELD DOWNL_PATH.
  IF DOWNL_PATH IS INITIAL.

*   Try to read "PathDownload"
    CALL METHOD CL_GUI_FRONTEND_SERVICES=>REGISTRY_GET_VALUE
      EXPORTING
        ROOT         = CL_GUI_FRONTEND_SERVICES=>HKEY_CURRENT_USER
        KEY          =
        'Software\SAP\SAPGUI Front\SAP Frontend Server\Filetransfer'
        VALUE        = 'PathDownload'
       IMPORTING
         REG_VALUE   = DL_PATH
         EXCEPTIONS
         GET_REGVALUE_FAILED  = 1
         CNTL_ERROR           = 2
         ERROR_NO_GUI         = 3
         NOT_SUPPORTED_BY_GUI = 4
         others               = 5.

*   Get current directory
    IF SY-SUBRC <> 0 OR DL_PATH = ''.
      CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_GET_CURRENT
        CHANGING
          CURRENT_DIRECTORY            = DL_PATH
        EXCEPTIONS
          DIRECTORY_GET_CURRENT_FAILED = 1
          CNTL_ERROR                   = 2
          ERROR_NO_GUI                 = 3
          NOT_SUPPORTED_BY_GUI         = 4
          others                       = 5.
      CALL METHOD CL_GUI_CFW=>FLUSH.

      CURRENT_DIR = DL_PATH.
    ENDIF.

    IF SY-SUBRC = 0.
      DOWNLOAD_PATH = DL_PATH.
    ENDIF.

  ELSE.
    DOWNLOAD_PATH = DOWNL_PATH.
  ENDIF.

* check if download path terminated with file separator
  LAST_CHAR_POS = STRLEN( DOWNLOAD_PATH ) - 1.

  IF LAST_CHAR_POS > 0.
    LAST_CHAR = DOWNLOAD_PATH+LAST_CHAR_POS(1).
  ELSE.
    LAST_CHAR = FILE_SEPARATOR.
  ENDIF.

  IF LAST_CHAR <> FILE_SEPARATOR.
    CONCATENATE DOWNLOAD_PATH FILE_SEPARATOR INTO DOWNLOAD_PATH.
  ENDIF.

*-Upload path-----------------------------------------------------------
  GET PARAMETER ID 'GR9' FIELD UPL_PATH.
  IF UPL_PATH IS INITIAL.

    CALL METHOD CL_GUI_FRONTEND_SERVICES=>REGISTRY_GET_VALUE
      EXPORTING
        ROOT          = CL_GUI_FRONTEND_SERVICES=>HKEY_CURRENT_USER
        KEY           =
        'Software\SAP\SAPGUI Front\SAP Frontend Server\Filetransfer'
        VALUE         = 'PathUpload'
       IMPORTING
         REG_VALUE    = UL_PATH
         EXCEPTIONS
         GET_REGVALUE_FAILED  = 1
         CNTL_ERROR           = 2
         ERROR_NO_GUI         = 3
         NOT_SUPPORTED_BY_GUI = 4
         others               = 5.

    IF SY-SUBRC <> 0 OR UL_PATH = ''.
      IF CURRENT_DIR <> ''.
        UL_PATH = CURRENT_DIR.
      ELSE.
        CALL METHOD CL_GUI_FRONTEND_SERVICES=>DIRECTORY_GET_CURRENT
          CHANGING
            CURRENT_DIRECTORY            = UL_PATH
          EXCEPTIONS
            DIRECTORY_GET_CURRENT_FAILED = 1
            CNTL_ERROR                   = 2
            ERROR_NO_GUI                 = 3
            NOT_SUPPORTED_BY_GUI         = 4
            others                       = 5.
        CALL METHOD CL_GUI_CFW=>FLUSH.
      ENDIF.
    ENDIF.

    IF SY-SUBRC = 0.
      UPLOAD_PATH = UL_PATH.
    ENDIF.

  ELSE.
    UPLOAD_PATH = UPL_PATH.
  ENDIF.

* check if upload path terminated with file separator
  LAST_CHAR_POS = STRLEN( UPLOAD_PATH ) - 1.

  IF LAST_CHAR_POS > 0.
    LAST_CHAR = UPLOAD_PATH+LAST_CHAR_POS(1).
  ELSE.
    LAST_CHAR = FILE_SEPARATOR.
  ENDIF.

  IF LAST_CHAR <> FILE_SEPARATOR.
    CONCATENATE UPLOAD_PATH FILE_SEPARATOR INTO UPLOAD_PATH.
  ENDIF.

endmethod.


METHOD GET_USER_NAME.

* ...

  CLASS CL_GUI_CONTROL DEFINITION LOAD .

  DATA: supported TYPE ABAP_BOOL.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'GET_USER_NAME'
    RECEIVING
      RESULT               = supported
    EXCEPTIONS
      CNTL_ERROR           = 1
      others               = 2.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF supported = abap_true.
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'GetUserName'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = USER_NAME
    EXCEPTIONS
      OTHERS     = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  ENDIF.

ENDMETHOD.                    "


method GET_WINDOWS_DIRECTORY.
* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.


  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
       METHOD  = 'GetWindowsDirectory'
       P_COUNT = 0
       QUEUE_ONLY = ' '
    IMPORTING
       RESULT = WINDOWS_DIRECTORY
    EXCEPTIONS
       OTHERS = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.


endmethod.                    "


method GUI_DOWNLOAD.
* ...

  CALL FUNCTION 'GUI_DOWNLOAD'
    EXPORTING
      BIN_FILESIZE              = BIN_FILESIZE
      FILENAME                  = FILENAME
      FILETYPE                  = FILETYPE
      APPEND                    = APPEND
      WRITE_FIELD_SEPARATOR     = WRITE_FIELD_SEPARATOR
      HEADER                    = HEADER
      TRUNC_TRAILING_BLANKS     = TRUNC_TRAILING_BLANKS
      WRITE_LF                  = WRITE_LF
      COL_SELECT                = COL_SELECT
      COL_SELECT_MASK           = COL_SELECT_MASK
      DAT_MODE                  = DAT_MODE
      CONFIRM_OVERWRITE         = CONFIRM_OVERWRITE
      NO_AUTH_CHECK             = NO_AUTH_CHECK
      CODEPAGE                  = CODEPAGE
      IGNORE_CERR               = IGNORE_CERR
      REPLACEMENT               = REPLACEMENT
      WRITE_BOM                 = WRITE_BOM
      TRUNC_TRAILING_BLANKS_EOL = TRUNC_TRAILING_BLANKS_EOL
      WK1_N_FORMAT              = WK1_N_FORMAT
      WK1_N_SIZE                = WK1_N_SIZE
      WK1_T_FORMAT              = WK1_T_FORMAT
      WK1_T_SIZE                = WK1_T_SIZE
      SHOW_TRANSFER_STATUS      = SHOW_TRANSFER_STATUS
      write_lf_after_last_line  = write_lf_after_last_line
      VIRUS_SCAN_PROFILE        = VIRUS_SCAN_PROFILE
    IMPORTING
      FILELENGTH                = FILELENGTH
    TABLES
      DATA_TAB                  = DATA_TAB
      FIELDNAMES                = FIELDNAMES
    EXCEPTIONS
      FILE_WRITE_ERROR          = 1
      NO_BATCH                  = 2
      GUI_REFUSE_FILETRANSFER   = 3
      INVALID_TYPE              = 4
      NO_AUTHORITY              = 5
      UNKNOWN_ERROR             = 6
      HEADER_NOT_ALLOWED        = 7
      SEPARATOR_NOT_ALLOWED     = 8
      FILESIZE_NOT_ALLOWED      = 9
      HEADER_TOO_LONG           = 10
      DP_ERROR_CREATE           = 11
      DP_ERROR_SEND             = 12
      DP_ERROR_WRITE            = 13
      UNKNOWN_DP_ERROR          = 14
      ACCESS_DENIED             = 15
      DP_OUT_OF_MEMORY          = 16
      DISK_FULL                 = 17
      DP_TIMEOUT                = 18
      FILE_NOT_FOUND            = 19
      DATAPROVIDER_EXCEPTION    = 20
      CONTROL_FLUSH_ERROR       = 21
      OTHERS                    = 22.

  IF SY-SUBRC <> 0.
    case sy-subrc.
      when 1.
        RAISE FILE_WRITE_ERROR.
      when 2.
        RAISE NO_BATCH.
      when 3.
        RAISE GUI_REFUSE_FILETRANSFER.
      when 4.
        RAISE INVALID_TYPE .
      when 5.
        RAISE NO_AUTHORITY.
      when 6.
        RAISE UNKNOWN_ERROR.
      when 7.
        RAISE HEADER_NOT_ALLOWED.
      when 8.
        RAISE SEPARATOR_NOT_ALLOWED.
      when 9.
        RAISE FILESIZE_NOT_ALLOWED.
      when 10.
        RAISE HEADER_TOO_LONG.
      when 11.
        RAISE DP_ERROR_CREATE.
      when 12.
        RAISE DP_ERROR_SEND.
      when 13.
        RAISE DP_ERROR_WRITE.
      when 14.
        RAISE UNKNOWN_DP_ERROR.
      when 15.
        RAISE ACCESS_DENIED.
      when 16.
        RAISE DP_OUT_OF_MEMORY.
      when 17.
        RAISE DISK_FULL.
      when 18.
        RAISE DP_TIMEOUT.
      when 19.
        RAISE FILE_NOT_FOUND.
      when 20.
        RAISE DATAPROVIDER_EXCEPTION.
      when 21.
        RAISE CONTROL_FLUSH_ERROR.
      when OTHERS.
        RAISE UNKNOWN_ERROR.
    endcase.
  ENDIF.

endmethod.


method GUI_UPLOAD.
* ...

CALL FUNCTION 'GUI_UPLOAD'
  EXPORTING
    FILENAME                      = FILENAME
    FILETYPE                      = FILETYPE
    HAS_FIELD_SEPARATOR           = HAS_FIELD_SEPARATOR
    HEADER_LENGTH                 = HEADER_LENGTH
    READ_BY_LINE                  = READ_BY_LINE
    DAT_MODE                      = DAT_MODE
    CODEPAGE                      = CODEPAGE
    IGNORE_CERR                   = IGNORE_CERR
    REPLACEMENT                   = REPLACEMENT
    VIRUS_SCAN_PROFILE            = VIRUS_SCAN_PROFILE
  IMPORTING
    FILELENGTH                    = FILELENGTH
    HEADER                        = HEADER
  TABLES
    DATA_TAB                      = DATA_TAB
  CHANGING
    ISSCANPERFORMED               = ISSCANPERFORMED
  EXCEPTIONS
    FILE_OPEN_ERROR               = 1
    FILE_READ_ERROR               = 2
    NO_BATCH                      = 3
    GUI_REFUSE_FILETRANSFER       = 4
    INVALID_TYPE                  = 5
    NO_AUTHORITY                  = 6
    UNKNOWN_ERROR                 = 7
    BAD_DATA_FORMAT               = 8
    HEADER_NOT_ALLOWED            = 9
    SEPARATOR_NOT_ALLOWED         = 10
    HEADER_TOO_LONG               = 11
    UNKNOWN_DP_ERROR              = 12
    ACCESS_DENIED                 = 13
    DP_OUT_OF_MEMORY              = 14
    DISK_FULL                     = 15
    DP_TIMEOUT                    = 16
    OTHERS                        = 17
    .

  IF SY-SUBRC <> 0.
    CASE SY-SUBRC.
      WHEN 1.
        RAISE FILE_OPEN_ERROR.
      WHEN 2.
        RAISE FILE_READ_ERROR.
      WHEN 3.
        RAISE NO_BATCH.
      WHEN 4.
        RAISE GUI_REFUSE_FILETRANSFER.
      WHEN 5.
        RAISE INVALID_TYPE.
      WHEN 6.
        RAISE NO_AUTHORITY.
      WHEN 7.
        RAISE UNKNOWN_ERROR.
      WHEN 8.
        RAISE BAD_DATA_FORMAT.
      WHEN 9.
        RAISE HEADER_NOT_ALLOWED.
      WHEN 10.
        RAISE SEPARATOR_NOT_ALLOWED.
      WHEN 11.
        RAISE HEADER_TOO_LONG.
      WHEN 12.
        RAISE UNKNOWN_DP_ERROR.
      WHEN 13.
        RAISE ACCESS_DENIED.
      WHEN 14.
        RAISE DP_OUT_OF_MEMORY.
      WHEN 15.
        RAISE DISK_FULL.
      WHEN 16.
        RAISE DP_TIMEOUT.
      WHEN OTHERS.
        RAISE UNKNOWN_ERROR.
    ENDCASE.
  ENDIF.


endmethod.


method IS_SCRIPTING_ACTIVE.

  DATA: feature_supported_b TYPE ABAP_BOOL.
  DATA: L_RESULT TYPE I.


  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING                          " check GUI screenshot support
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'IS_SCRIPTING_ACTIVE'
    RECEIVING
      RESULT               = feature_supported_b
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF ( SY-SUBRC <> 0 ) OR ( feature_supported_b = ABAP_FALSE ).
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

      CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'IsScriptingActive'
        P_COUNT = 0
      IMPORTING
        RESULT     = L_RESULT
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    IF L_RESULT = 0.
      RESULT = 0.
    ELSE.
      RESULT = 1.
    ENDIF.

endmethod.


method IS_TERMINAL_SERVER.
* ...

  DATA: L_RESULT TYPE I.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD     = 'IsTerminalServicesRunning'
      P_COUNT    = 0
      QUEUE_ONLY = ' '
    IMPORTING
      RESULT     = L_RESULT
    EXCEPTIONS
      OTHERS     = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.
  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF L_RESULT = 0.
    CLEAR RESULT.
  ELSE.
    RESULT = 'X'.
  ENDIF.

endmethod.                    "IS_TERMINAL_SERVER


method IS_VALID_HANDLE.

* check class constructor error code
  RCODE = ERROR_CODE.

  IF ERROR_CODE = ERROR_NOT_SUPPORTED_BY_GUI.
    RCODE = ERROR_NOT_SUPPORTED_BY_GUI.
  ELSEIF  ERROR_CODE = ERROR_NO_GUI.
    RCODE = ERROR_NO_GUI.
  ENDIF.

endmethod.


method RAISE_SCRIPTING_EVENT.

  DATA: feature_supported_b TYPE ABAP_BOOL.


  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING                          " check GUI screenshot support
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'RAISE_SCRIPTING_EVENT'
    RECEIVING
      RESULT               = feature_supported_b
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF ( SY-SUBRC <> 0 ) OR ( feature_supported_b = ABAP_FALSE ).
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

      CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'RaiseScriptingEvent'
        P1      = PARAMS
        P_COUNT = 1
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

endmethod.


METHOD REGISTRY_DELETE_KEY.

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF KEY IS INITIAL.
    RAISE BAD_PARAMETER.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'DeleteRegKey'
      P1      = ROOT
      P2      = KEY
      P_COUNT = 2
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "REGISTRY_DELETE_KEY


METHOD REGISTRY_DELETE_VALUE .

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF VALUE IS INITIAL.
    RAISE REGISTRY_DELETE_VALUE_FAILED.
  ENDIF.

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'DeleteRegValue'
      P1      = ROOT
      P2      = KEY
      P3      = VALUE
      P_COUNT = 3
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

ENDMETHOD.                    "REGISTRY_DELETE_VALUE


method REGISTRY_GET_DWORD_VALUE .
* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF VALUE IS INITIAL.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetRegDWValueEx'
        P1      = ROOT
        P2      = KEY
        P3      = ''
        P_COUNT = 3
      IMPORTING
        RESULT  = REG_VALUE
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'GetRegDWValueEx'
        P1      = ROOT
        P2      = KEY
        P3      = VALUE
        P_COUNT = 3
      IMPORTING
        RESULT  = REG_VALUE
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

endmethod.                    "


METHOD REGISTRY_GET_VALUE .
* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

* TODO better error checking

  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'GetRegValueEx'
      P1      = ROOT
      P2      = KEY
      P3      = VALUE
      P_COUNT = 3
    IMPORTING
      RESULT  = REG_VALUE
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  if no_flush is initial.
    CALL METHOD CL_GUI_CFW=>FLUSH
      EXCEPTIONS
        CNTL_SYSTEM_ERROR = 1
        CNTL_ERROR        = 2
        others            = 3.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.
  endif.
ENDMETHOD.                    "


method REGISTRY_SET_DWORD_VALUE .
* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF VALUE IS INITIAL.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'SetRegDWValueEx'
        P1      = ROOT
        P2      = KEY
        P3      = ''
        P4      = DWORD_VALUE
        P_COUNT = 4
      IMPORTING
        RESULT  = RC
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'SetRegDWValueEx'
        P1      = ROOT
        P2      = KEY
        P3      = VALUE
        P4      = DWORD_VALUE
        P_COUNT = 4
      IMPORTING
        RESULT  = RC
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.


endmethod.                    "


METHOD REGISTRY_SET_VALUE .

* ...

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0.
    RAISE CNTL_ERROR.
  ENDIF.

  IF VALUE IS INITIAL.
    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'SetRegValue'
        P1      = ROOT
        P2      = KEY
        P3      = VALUE
        P_COUNT = 3
      IMPORTING
        RESULT  = RC
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ELSE.

    CALL METHOD HANDLE->CALL_METHOD
      EXPORTING
        METHOD  = 'SetRegValueEx'
        P1      = ROOT
        P2      = KEY
        P3      = VALUE_NAME
        P4      = VALUE
        P_COUNT = 4
      IMPORTING
        RESULT  = RC
      EXCEPTIONS
        OTHERS  = 1.

    IF SY-SUBRC <> 0.
      RAISE CNTL_ERROR.
    ENDIF.

  ENDIF.

ENDMETHOD.                    "


METHOD show_document.
* This method provides a safer way for applications to display documents
* at the front end side. It is created to replace the old way of calling
* GUI_DOWNLOAD and EXECUTE, which required execute permissions for viewing
* documents.
*
* The treatment of the DOCUMENT_DATA internal table is the same as
* in GUI_DOWNLOAD.
*
* DOCUMENT_NAME is mandatory. The following character set is allowed
* for document name: a-zA-Z0-9-_.#'~()!@$€+=;&,{}[]^°²³%&§`´ and space.
* National letters like öÄßé etc. can be used. The DOCUMENT_NAME must not start or end with
* a space.
*
* The document gets downloaded in the SAP GUI temp directory. If such
* a file exists already, a new name is generated by adding consequent
* numbers in the form Filename-1.ext, Filename-2.ext etc.
*
* MIME_TYPE should be provided but it can be empty. It determines what
* viewer will be started on the client side according to the MIME type
* associations. If empty, the client will try to infer the MIME type
* from the document contents.
*
* If the front end does not support ShowDocument, a fallback server-side
* method will be used. In that scenario MIME_TYPE is ignored.
*
* KEEP_FILE is a boolean flag that can be used to keep the viewed file
* without cleaning it up. The stored document path is returned in TEMP_FILE_PATH.
*
* Example usage:
*
*DATA: lt_document_data TYPE STANDARD TABLE,
*      lv_filesize      TYPE i,
*      lv_saved_doc     TYPE string.
*
*" Import data from the database here.
*
*CALL METHOD cl_gui_frontend_services=>show_document
*  EXPORTING
*    document_name         = 'test.pdf'
*    mime_type             = 'application/pdf'
*    data_length           = lv_filesize
*    keep_file             = 1
*  CHANGING
*    document_data         = lt_document_data
*  IMPORTING
*    temp_file_path        = lv_saved_doc
*  EXCEPTIONS
*    cntl_error            = 1
*    error_no_gui          = 2
*    bad_parameter         = 3
*    error_writing_data    = 4
*    error_starting_viewer = 5
*    unknown_mime_type     = 6
*    not_supported_by_gui  = 7
*    access_denied         = 8
*    OTHERS                = 9.
*
*IF sy-subrc <> 0.
*   " Handle errors here
*ENDIF.
*


  "---------------------------------------------------------------------
  " validate authority
  "---------------------------------------------------------------------

  AUTHORITY-CHECK OBJECT 'S_GUI'
                      ID 'ACTVT'
                   FIELD '04'.   " Print, show_document, etc.

  IF sy-subrc <> 0.
    RAISE no_authority.
  ENDIF.

  "---------------------------------------------------------------------
  " check if running in batch mode
  "---------------------------------------------------------------------
  DATA: gui_available_b TYPE char1.

  CALL FUNCTION 'GUI_IS_AVAILABLE'
    IMPORTING
      return = gui_available_b.

  IF gui_available_b IS INITIAL.
    RAISE error_no_gui.
  ENDIF.

  "---------------------------------------------------------------------
  " parameter checking
  "---------------------------------------------------------------------

  IF data_length LT 0.
    RAISE bad_parameter.
  ENDIF.

  " Allowed characters (additional to standard alphanumerics) for document name: -_.#'~()!@$€+=;,{}[]^°²³%&§`´
  " The document name may contain spaces, but not in the beginning or in the end.
  CONSTANTS: guter_zeichensatz TYPE string VALUE '\w\-\.\''\#\~\(\)\!\@\$\€\+\=\;\,\{\}\[\]\^\°\²\³\%\&\§\`\´' ##STRING_OK.

  DATA:      regex      TYPE string,
             docname_ok TYPE abap_bool.

  CONCATENATE '^[' guter_zeichensatz ']('     " one non-space allowed char in the beginning
                 '[\s' guter_zeichensatz ']*' " following we may have space/non-space allowed chars
                 '[' guter_zeichensatz ']'    " in the end the last char of the optional tail must be non-space.
              ')?$'
            INTO regex.

  docname_ok = cl_abap_matcher=>matches( pattern     = regex
                                         text        = document_name
                                         ignore_case = abap_true ).

  IF docname_ok NE abap_true.
    RAISE bad_parameter.
  ENDIF.

*  " Uncomment if MIME type should be mandatory.
*  IF mime_type EQ ''.
*    RAISE bad_parameter.
*  ENDIF.

  "---------------------------------------------------------------------
  " check the support bit if the method ShowDocument is present in front
  "---------------------------------------------------------------------
  DATA: feature_supported_b TYPE abap_bool.

  CALL METHOD cl_gui_frontend_services=>check_gui_support
    EXPORTING
      component            = 'sapinfocntl'
      feature_name         = 'SHOWDOCUMENT'
    RECEIVING
      result               = feature_supported_b
    EXCEPTIONS      "cntl_error           = 1   " These exceptions need to be passed directly.
                                                                  "error_no_gui         = 2
      wrong_parameter      = 3
      not_supported_by_gui = 4
      unknown_error        = 5
      OTHERS               = 6.

  IF ( sy-subrc <> 0 ) OR ( feature_supported_b = abap_false ).

    " Delegate to the fall back method, if the feature is not supported.
    CALL METHOD cl_gui_frontend_services=>show_document_fallback
      EXPORTING
        document_name = document_name
        mime_type     = mime_type
        data_length   = data_length
      CHANGING
        document_data = document_data.

    RETURN.

  ENDIF.


  "---------------------------------------------------------------------
  " the client supports ShowDocument
  "---------------------------------------------------------------------
  DATA: " Data provider URL that will be used to locate
        " the downloaded resource at the frontend side.
        lv_data_provider_url(256) TYPE c,

        " Return code
        lv_ret_str                TYPE string,
        lv_rc_str                 TYPE string,
        lv_rc                     TYPE i.


  IF cl_gui_control=>www_active IS NOT INITIAL.

    CALL FUNCTION 'ITS_SHOW_DOCUMENT'
      EXPORTING
        DOCUMENT_NAME              = DOCUMENT_NAME
        MIME_TYPE                  = MIME_TYPE
        DATA_LENGTH                = DATA_LENGTH
*       DOC_TYPE                   = 'BIN'
        KEEP_FILE                  = KEEP_FILE
      IMPORTING
        RET_STR                    = lv_ret_str
      TABLES
        DOCUMENT_DATA              = DOCUMENT_DATA
      EXCEPTIONS
        CNTL_ERROR                 = 1
        ERROR_WRITING_DATA         = 2
        NOT_SUPPORTED_BY_GUI       = 3
        OTHERS                     = 4
              .
    CASE sy-subrc.
      WHEN 0.
      WHEN 2.
        RAISE error_writing_data.
      WHEN OTHERS.
        RAISE cntl_error.
    ENDCASE.

  ELSE.
    "--------------------------
    " Java GUI and Windows GUI
    "--------------------------

    " Push the document data into the data provider.
    " It will return a URL that can be passed to the frontend
    " and there we can use it to load the data and save it to
    " a temporary file.
    CALL FUNCTION 'DP_CREATE_URL'
      EXPORTING
        type                 = 'APPLICATION'
        subtype              = 'X-UNKNOWN'
        send_data_as_string  = ' '
        size                 = data_length
      TABLES
        data                 = document_data
      CHANGING
        url                  = lv_data_provider_url
      EXCEPTIONS
        dp_invalid_parameter = 1
        dp_error_put_table   = 2
        dp_error_general     = 3
        OTHERS               = 4.

    CASE sy-subrc.
      WHEN 0.
      WHEN 2.
        RAISE error_writing_data.
      WHEN 3.
        RAISE error_writing_data.
      WHEN OTHERS.
        RAISE cntl_error.
    ENDCASE.

    " At this point the table is pushed into the data provider.

    DATA: lv_keep_file TYPE i VALUE 0.
    IF keep_file EQ 'X'.
      lv_keep_file = 1.
    ENDIF.

    " Make an InfoCtrl call to display the document.
    CALL METHOD handle->call_method
      EXPORTING
        method            = 'ShowDocument'
        p_count           = 5
        p1                = lv_data_provider_url
        p2                = data_length
        p3                = document_name
        p4                = mime_type
        p5                = lv_keep_file
        queue_only        = ' '
      IMPORTING
        result            = lv_ret_str
      EXCEPTIONS
        cntl_error        = 1
        cntl_system_error = 2
        OTHERS            = 3.

    IF sy-subrc NE 0.
      RAISE cntl_error.
    ENDIF.

    CALL METHOD cl_gui_cfw=>flush
      EXCEPTIONS
        cntl_error = 1
        OTHERS     = 2.

    IF sy-subrc NE 0.
      RAISE cntl_error.
    ENDIF.

  ENDIF.

* Parse return code.
  SPLIT lv_ret_str AT ';'
    INTO lv_rc_str temp_file_path.

  lv_rc = lv_rc_str.

*Rc =
*  0: OK
*  1: Can't write temporary data
*  2: Can't access data provider data
*  3: Can't open associated application
*  4: Unknown mime type
*  5: Access denied
*  100: Unspecified error
  CASE lv_rc.
    WHEN 0.
    WHEN 1.
      RAISE error_writing_data.
    WHEN 2.
      RAISE error_writing_data.
    WHEN 3.
      RAISE error_starting_viewer.
    WHEN 4.
      RAISE unknown_mime_type.
    WHEN 5.
      RAISE access_denied.
    WHEN OTHERS.
      RAISE cntl_error.
  ENDCASE.

ENDMETHOD.


METHOD show_document_fallback.

  CONSTANTS: tmp_filename_max_attempts TYPE i VALUE 10000000.

  DATA: lv_tempname       TYPE string,
        lv_file_separator TYPE c VALUE '/'.

  "---------------------------------------------------------------------
  " file separator
  "---------------------------------------------------------------------
  CALL METHOD cl_gui_frontend_services=>get_file_separator
    CHANGING
      file_separator = lv_file_separator.

  "---------------------------------------------------------------------
  " gui temp directory
  "---------------------------------------------------------------------
  CALL METHOD cl_gui_frontend_services=>get_temp_directory
    CHANGING
      temp_dir             = lv_tempname
    EXCEPTIONS
      cntl_error           = 1
      error_no_gui         = 2
      not_supported_by_gui = 3
      OTHERS               = 4.

  DATA: lv_tempsubrc LIKE sy-subrc.
  lv_tempsubrc = sy-subrc.

  cl_gui_cfw=>flush( ).

  IF lv_tempsubrc NE 0 OR lv_tempname IS INITIAL.
    RAISE error_writing_data.
  ENDIF.

  "---------------------------------------------------------------------
  " list files
  "---------------------------------------------------------------------
  DATA: lt_files      TYPE STANDARD TABLE OF file_info,
        lv_filescount TYPE i.

  CALL METHOD cl_gui_frontend_services=>directory_list_files
    EXPORTING
      directory                   = lv_tempname
*     filter                      = '*.*'
*     files_only                  =
*     directories_only            =
    CHANGING
      file_table                  = lt_files
      count                       = lv_filescount
    EXCEPTIONS
*     cntl_error                  = 1
*     directory_list_files_failed = 2
*     wrong_parameter             = 3
*     error_no_gui                = 4
*     not_supported_by_gui        = 5
      OTHERS                      = 6.
  IF sy-subrc <> 0.
    RAISE error_writing_data.
  ENDIF.

  "---------------------------------------------------------------------
  " search files
  "---------------------------------------------------------------------

  DATA: lv_filename     TYPE string,
      lv_extension    TYPE string,
      lv_filename_alt TYPE string.

  " This regular expression will set either lv_filename and
  " lv_extension, or lv_filename_alt (if there is no extension).
  FIND REGEX      '(.*)(\.[^.]*)$|(.*)'
       IN         document_name
       SUBMATCHES lv_filename
                  lv_extension
                  lv_filename_alt.

  IF lv_filename IS INITIAL.
    lv_filename = lv_filename_alt. " Only filename without extension
  ENDIF.

  DATA: lv_found        TYPE abap_bool VALUE abap_false,
        lv_tmp_filename TYPE string.

  DO tmp_filename_max_attempts TIMES.

    DATA: ls_fileinfo  LIKE LINE OF lt_files,
          lv_index_str TYPE string.

    IF sy-index NE 0.
      lv_index_str = sy-index.
      CONDENSE lv_index_str.
      CONCATENATE lv_filename '-' lv_index_str lv_extension
             INTO lv_tmp_filename.
    ELSE.
      " We don't want a number the first attempt
      " (document-0.txt is not needed, use document.txt).
      lv_tmp_filename = document_name.
    ENDIF.

    DATA: lv_name_exists TYPE abap_bool.
    lv_name_exists = abap_false.

    LOOP AT lt_files INTO ls_fileinfo.

      DATA: lv_ci_equal TYPE abap_bool,
            lv_current_filename TYPE string.

      lv_current_filename = ls_fileinfo-filename.

      CALL METHOD cl_gui_frontend_services=>strcmpi
        EXPORTING
          text1  = lv_tmp_filename
          text2  = lv_current_filename
        IMPORTING
          result = lv_ci_equal.

      IF lv_ci_equal EQ abap_true.
        lv_name_exists = abap_true.
        EXIT.
      ENDIF.

    ENDLOOP.

    IF lv_name_exists EQ abap_false.
      " Found a non-existing name.
      lv_found = abap_true.
      EXIT.
    ENDIF.

  ENDDO. "DO tmp_filename_max_attempts TIMES.

  IF lv_found EQ abap_false.
    RAISE error_writing_data.
  ENDIF.

  "---------------------------------------------------------------------
  " gui_download
  "---------------------------------------------------------------------
  DATA: lv_tmp_fullpath TYPE string.
  CONCATENATE lv_tempname lv_file_separator lv_tmp_filename INTO lv_tmp_fullpath.

  CALL METHOD cl_gui_frontend_services=>gui_download
    EXPORTING
      bin_filesize = data_length
      filename     = lv_tmp_fullpath
      filetype     = 'BIN'
    CHANGING
      data_tab     = document_data
    EXCEPTIONS
      OTHERS       = 24.

  IF sy-subrc <> 0.
    RAISE error_writing_data.
  ENDIF.

  "---------------------------------------------------------------------
  " execute
  "---------------------------------------------------------------------
  CALL METHOD cl_gui_frontend_services=>execute
    EXPORTING
      document      = lv_tmp_fullpath
*     operation     = 'OPEN'
    EXCEPTIONS
      cntl_error    = 1
      bad_parameter = 3
      OTHERS        = 10.

  CASE sy-subrc.
    WHEN 0.
    WHEN 1.
      RAISE cntl_error.
    WHEN 3.
      RAISE cntl_error.
    WHEN 10.
      RAISE error_starting_viewer.
    WHEN OTHERS.
      RAISE error_starting_viewer.
  ENDCASE.

ENDMETHOD.                    "show_document_fallback


METHOD strcmpi.

  DATA: t1uc LIKE text1,
        t2uc LIKE text2.

  t1uc = text1.
  t2uc = text2.

  TRANSLATE t1uc TO UPPER CASE.
  TRANSLATE t2uc TO UPPER CASE.

  IF t1uc EQ t2uc.
    result = abap_true.
  ELSE.
    result = abap_false.
  ENDIF.

ENDMETHOD.


method TYPEAHEAD_EXPORT.
* ...

  DATA: table_ref TYPE REF TO data.
  FIELD-SYMBOLS <table> TYPE STANDARD TABLE.
  CLASS CL_GUI_CONTROL DEFINITION LOAD .
  DATA: RC.
  DATA: feature_supported_b TYPE ABAP_BOOL.

* check class constructor error code
  IF IS_VALID_HANDLE( ) NE 0 AND CL_GUI_CONTROL=>WWW_ACTIVE IS INITIAL.
    RAISE CNTL_ERROR.
  ENDIF.


  CALL METHOD CL_GUI_FRONTEND_SERVICES=>CHECK_GUI_SUPPORT
    EXPORTING                          " check GUI screenshot support
      COMPONENT            = 'sapinfocntl'
      FEATURE_NAME         = 'TYPEAHEAD_EXPORT'
    RECEIVING
      RESULT               = feature_supported_b
    EXCEPTIONS
      CNTL_ERROR           = 1
      ERROR_NO_GUI         = 2
      WRONG_PARAMETER      = 3
      NOT_SUPPORTED_BY_GUI = 4
      UNKNOWN_ERROR        = 5
      others               = 6.

  IF ( SY-SUBRC <> 0 ) OR ( feature_supported_b = ABAP_FALSE ).
    RAISE NOT_SUPPORTED_BY_GUI.
  ENDIF.

* send data to frontend
  CALL FUNCTION 'DP_STRETCH_SIMPLE_TABLE'
    EXPORTING
      copy_lines             = 'X'
    IMPORTING
      stretched_data_ref     = table_ref
    TABLES
      data                   = data
    EXCEPTIONS
      DP_ERROR_MULTIPLE_COLS = 1
      DP_ERROR_NOT_CHARLIKE  = 2.

  IF sy-subrc = 0.
    ASSIGN table_ref->* TO <table>.
  ELSE.
    ASSIGN data TO <table>.
  ENDIF.

* special handling for SAPGUI for HTML
  IF CL_GUI_CONTROL=>WWW_ACTIVE IS NOT INITIAL.
    data dp type cntl_handle.
    data response_string type string.
    data ta_data_descr TYPE REF TO cl_abap_typedescr.

    DATA(writer) = cl_sxml_string_writer=>create(
      type = if_sxml=>co_xt_json ).
    CALL TRANSFORMATION id SOURCE itab = data
                           RESULT XML writer.
    DATA(json) = writer->get_output( ).

    CALL FUNCTION 'ITS_EXPORT_TYPEAHEAD'
      DESTINATION 'SAPGUI'
      EXPORTING
        TA_DATA = json.

  ELSE.

  CALL FUNCTION 'DP_CONTROL_ASSIGN_TABLE'
    EXPORTING
      H_CNTL                 = HANDLE->H_CONTROL
      MEDIUM                 = CNDP_MEDIUM_R3TABLE
      PROPERTYNAME           = 'ClipBoardDataTable'
    TABLES
      DATA                   = <table>
    EXCEPTIONS
      DP_ERROR_CREATE        = 1
      DP_ERROR_SEND_DATA     = 2
      DP_ERROR_ASSIGN        = 3
      DP_ERROR_INVALID_PARAM = 4
      DP_ERROR_TABNAME       = 5
      OTHERS                 = 6.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

* fill file table at frontend
  CALL METHOD HANDLE->CALL_METHOD
    EXPORTING
      METHOD  = 'TypeAheadExport'
      P_COUNT = 0
    IMPORTING
      RESULT  = RC
    EXCEPTIONS
      OTHERS  = 1.

  IF SY-SUBRC <> 0.
    RAISE CNTL_ERROR.
  ENDIF.

  CALL METHOD CL_GUI_CFW=>FLUSH
    EXCEPTIONS
      CNTL_SYSTEM_ERROR = 1
      CNTL_ERROR        = 2
      others            = 3.


  ENDIF.

  IF SY-SUBRC <> 0 OR RC = -1.
    RAISE CNTL_ERROR.
  ENDIF.

endmethod.
ENDCLASS.
