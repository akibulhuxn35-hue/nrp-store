package com.nrpstore.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebSettings;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String HOME = "https://nrp-store.onrender.com";
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermission;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equals(uri.getScheme()) &&
                    ("nrp-store.onrender.com".equals(uri.getHost()))) {
                    return false;
                }
                // Keep external links outside the app.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) { }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = params.createIntent();
                try {
                    startActivityForResult(intent, 100);
                    return true;
                } catch (Exception e) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "File picker unavailable", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                boolean trusted = request.getOrigin() != null &&
                    "https://nrp-store.onrender.com".equals(request.getOrigin().toString());
                if (!trusted) {
                    request.deny();
                    return;
                }
                pendingPermission = request;
                if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    grantCamera(request);
                } else {
                    requestPermissions(new String[]{Manifest.permission.CAMERA}, 200);
                }
            }
        });

        if (savedInstanceState == null) {
            webView.loadUrl(HOME);
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private void grantCamera(PermissionRequest request) {
        for (String resource : request.getResources()) {
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)) {
                request.grant(new String[]{resource});
                return;
            }
        }
        request.deny();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == 200 && pendingPermission != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
                grantCamera(pendingPermission);
            } else {
                pendingPermission.deny();
            }
            pendingPermission = null;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 100 && fileCallback != null) {
            Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) webView.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
