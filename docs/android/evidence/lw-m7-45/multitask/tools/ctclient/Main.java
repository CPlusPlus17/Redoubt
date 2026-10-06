package org.redoubt.ctclient;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.TextView;

/** Test-only Custom Tabs client: opens the given URL as a custom tab in THIS task (no NEW_TASK). */
public class Main extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        TextView t = new TextView(this);
        t.setText("CT client");
        setContentView(t);
        String url = getIntent().getStringExtra("url");
        if (url == null) return;
        Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        i.setPackage("org.redoubtbrowser");
        Bundle extras = new Bundle();
        extras.putBinder("android.support.customtabs.extra.SESSION", null);
        i.putExtras(extras);
        startActivity(i);
    }
}
