package ai.indra.origo.remote

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.View
import android.view.ViewGroup
import android.view.Gravity
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebSettings
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import android.content.Intent
import android.net.Uri
import android.Manifest
import android.content.pm.PackageManager
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.CookieManager
import android.webkit.WebStorage
import android.net.http.SslError
import android.webkit.SslErrorHandler
import android.webkit.WebResourceResponse

/**
 * Secure-by-default remote shell for the user's own Origo workstation.
 * Pairing stores only the user's private HTTPS endpoint; no shared vendor server exists.
 */
class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("origo_remote", MODE_PRIVATE) }
    private lateinit var root: LinearLayout
    private lateinit var web: WebView
    private lateinit var status: TextView
    private lateinit var address: EditText
    private lateinit var connectButton: Button
    private var baseUrl: String = ""
    private var pendingFile: ValueCallback<Array<Uri>>? = null
    private var pendingMicrophone: PermissionRequest? = null
    private var mainFrameFailed = false
    private val fileRequestCode = 21
    private val microphoneRequestCode = 22

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(11, 16, 21)
        window.navigationBarColor = Color.rgb(11, 16, 21)
        baseUrl = prefs.getString("base_url", "") ?: ""
        buildUi()
        if (baseUrl.isNotBlank()) connect(baseUrl, save = false)
    }

    private fun buildUi() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(11, 16, 21))
        }
        val header = TextView(this).apply {
            text = "◈  INDRA ORIGO  /  REMOTE"
            setTextColor(Color.rgb(118, 247, 196)); textSize = 16f
            setPadding(18, 18, 18, 14)
        }
        root.addView(header)
        val setup = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18, 8, 18, 14)
        }
        val title = TextView(this).apply {
            text = "Connect to your workstation"
            setTextColor(Color.WHITE); textSize = 22f
        }
        setup.addView(title)
        val instructions = TextView(this).apply {
            text = "Keep your PC running and connect your phone to the same private Tailscale network. Paste the HTTPS address shown by the Origo PC pairing setup."
            setTextColor(Color.rgb(177, 191, 200)); textSize = 14f
            setPadding(0, 8, 0, 12)
        }
        setup.addView(instructions)
        address = EditText(this).apply {
            hint = "https://your-pc.your-tailnet.ts.net"
            setHintTextColor(Color.rgb(120, 136, 146)); setTextColor(Color.WHITE)
            setSingleLine(true); textSize = 14f
            setPadding(12, 8, 12, 8)
            setBackgroundColor(Color.rgb(25, 34, 42))
            if (baseUrl.isNotBlank()) setText(baseUrl)
        }
        setup.addView(address, LinearLayout.LayoutParams(-1, 52))
        connectButton = Button(this).apply {
            text = "Connect securely"
            setOnClickListener { connect(address.text.toString().trim(), save = true) }
        }
        setup.addView(connectButton, LinearLayout.LayoutParams(-1, 52).apply { topMargin = 8 })
        setup.addView(Button(this).apply {
            text = "Disconnect and forget this workstation"
            setOnClickListener { disconnect() }
        })
        status = TextView(this).apply {
            text = "Not connected · Your endpoint stays on this device"
            setTextColor(Color.rgb(177, 191, 200)); textSize = 12f
            setPadding(0, 8, 0, 4)
        }
        setup.addView(status)
        root.addView(setup)
        web = WebView(this)
        web.setBackgroundColor(Color.rgb(11, 16, 21))
        configureWebView(web.settings)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false)
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView?, callback: ValueCallback<Array<Uri>>?, params: FileChooserParams?): Boolean {
                pendingFile?.onReceiveValue(null)
                pendingFile = null
                if (!EndpointPolicy.sameOrigin(web.url ?: "", baseUrl)) {
                    callback?.onReceiveValue(null)
                    return true
                }
                pendingFile = callback
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    val accepted = params?.acceptTypes?.filter { it.contains('/') && !it.contains(';') }?.toTypedArray()
                    if (!accepted.isNullOrEmpty()) putExtra(Intent.EXTRA_MIME_TYPES, accepted)
                }
                try { startActivityForResult(intent, fileRequestCode) }
                catch (_: android.content.ActivityNotFoundException) {
                    pendingFile?.onReceiveValue(null); pendingFile = null
                    status.text = "No document picker is available on this device."
                }
                return true
            }

            override fun onPermissionRequest(request: PermissionRequest?) {
                if (request == null) return
                if (!EndpointPolicy.sameOrigin(request.origin.toString(), baseUrl) ||
                    !EndpointPolicy.sameOrigin(web.url ?: "", baseUrl) ||
                    request.resources.toSet() != setOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                    request.deny(); return
                }
                pendingMicrophone?.deny()
                pendingMicrophone = request
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)); pendingMicrophone = null
                } else requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), microphoneRequestCode)
            }

            override fun onPermissionRequestCanceled(request: PermissionRequest?) {
                if (pendingMicrophone === request) pendingMicrophone = null
            }
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return true
                if (EndpointPolicy.sameOrigin(uri.toString(), baseUrl)) return false
                // External HTTPS links open in the system browser; never navigate the trusted WebView off-origin.
                if (request.isForMainFrame && request.hasGesture() && uri.scheme == "https") {
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                }
                return true
            }
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                if (baseUrl.isEmpty()) return
                mainFrameFailed = false
                status.text = "Connecting to your private workstation…"
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                if (baseUrl.isEmpty()) return
                if (mainFrameFailed) return
                val current = runCatching { Uri.parse(url ?: "") }.getOrNull()
                status.text = if (current?.path?.contains("login") == true) {
                    "Sign-in required · use your workstation's configured sign-in"
                } else {
                    "Connected · ${Uri.parse(baseUrl).host ?: "workstation"}"
                }
                connectButton.text = "Reconnect"
            }
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: android.webkit.WebResourceError?) {
                if (request?.isForMainFrame == true) {
                    mainFrameFailed = true
                    status.text = "Can't reach PC. Check that it is on, Origo is running, and Tailscale is connected."
                }
            }
            override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, response: WebResourceResponse?) {
                if (request?.isForMainFrame == true) {
                    mainFrameFailed = true
                    status.text = "Workstation returned HTTP ${response?.statusCode}. Check the PC's remote-access setup."
                }
            }
            override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, error: SslError?) {
                handler?.cancel()
                mainFrameFailed = true
                status.text = "Secure connection failed. Check the workstation's HTTPS certificate."
            }
        }
        root.addView(web, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView(settings: WebSettings) {
        settings.javaScriptEnabled = true // Required by Origo's existing web UI.
        settings.domStorageEnabled = true
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.javaScriptCanOpenWindowsAutomatically = false
        settings.setSupportMultipleWindows(false)
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.safeBrowsingEnabled = true
        settings.userAgentString = settings.userAgentString + " OrigoRemote/1.1"
    }

    private fun connect(raw: String, save: Boolean) {
        val safe = EndpointPolicy.normalize(raw)
        if (safe == null) {
            Toast.makeText(this, "Use your workstation's HTTPS Tailscale address (…ts.net). Custom ports and URL paths are not allowed.", Toast.LENGTH_LONG).show()
            return
        }
        baseUrl = safe
        pendingMicrophone?.deny(); pendingMicrophone = null
        pendingFile?.onReceiveValue(null); pendingFile = null
        address.setText(safe)
        if (save) prefs.edit().putString("base_url", safe).apply()
        status.text = "Checking workstation…"
        connectButton.isEnabled = false
        // The web UI is only loaded from the configured HTTPS endpoint.
        web.loadUrl(safe)
        connectButton.postDelayed({ connectButton.isEnabled = true }, 1200)
    }

    private fun disconnect() {
        pendingMicrophone?.deny(); pendingMicrophone = null
        pendingFile?.onReceiveValue(null); pendingFile = null
        baseUrl = ""
        prefs.edit().remove("base_url").apply()
        web.stopLoading(); web.loadUrl("about:blank"); web.clearHistory(); web.clearCache(true)
        CookieManager.getInstance().removeAllCookies { CookieManager.getInstance().flush() }
        WebStorage.getInstance().deleteAllData()
        address.setText("")
        status.text = "Disconnected · workstation sign-in and saved address cleared"
        connectButton.text = "Connect securely"
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != fileRequestCode) return
        val callback = pendingFile ?: return
        pendingFile = null
        val selected = data?.data
        callback.onReceiveValue(if (resultCode == RESULT_OK && selected?.scheme == "content" &&
            EndpointPolicy.sameOrigin(web.url ?: "", baseUrl)) arrayOf(selected) else null)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != microphoneRequestCode) return
        val request = pendingMicrophone ?: return
        pendingMicrophone = null
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED &&
            EndpointPolicy.sameOrigin(request.origin.toString(), baseUrl) &&
            EndpointPolicy.sameOrigin(web.url ?: "", baseUrl)) {
            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
        } else {
            request.deny()
            status.text = "Microphone access was not granted. Text and attachments still work."
        }
    }

    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        if (::web.isInitialized) {
            pendingFile?.onReceiveValue(null); pendingFile = null
            pendingMicrophone?.deny(); pendingMicrophone = null
            web.stopLoading(); web.loadUrl("about:blank"); web.clearHistory(); web.removeAllViews(); web.destroy()
        }
        super.onDestroy()
    }
}
