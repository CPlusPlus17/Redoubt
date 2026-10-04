/* Stand-in for Robolectric's runner: UpdateCheckerTest needs no Android
 * runtime beyond android.util.Base64 (shimmed) and org.json (the real library). */
package org.robolectric

class RobolectricTestRunner(klass: Class<*>) : org.junit.runners.BlockJUnit4ClassRunner(klass)
