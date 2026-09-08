import java.nio.file.*;
import org.jetbrains.kotlin.cli.jvm.compiler.KotlinCoreEnvironment;
import org.jetbrains.kotlin.cli.jvm.compiler.EnvironmentConfigFiles;
import org.jetbrains.kotlin.config.CompilerConfiguration;
import org.jetbrains.kotlin.com.intellij.openapi.util.Disposer;
import org.jetbrains.kotlin.com.intellij.psi.PsiErrorElement;
import org.jetbrains.kotlin.com.intellij.psi.util.PsiTreeUtil;
import org.jetbrains.kotlin.psi.KtPsiFactory;

public class KotlinSyntax {
  public static void main(String[] args) throws Exception {
    var disposable = Disposer.newDisposable();
    int errors = 0;
    try {
      var environment = KotlinCoreEnvironment.createForProduction(disposable, new CompilerConfiguration(), EnvironmentConfigFiles.JVM_CONFIG_FILES);
      var factory = new KtPsiFactory(environment.getProject(), false);
      for (String file : args) {
        var parsed = factory.createFile(Path.of(file).getFileName().toString(), Files.readString(Path.of(file)));
        for (var error : PsiTreeUtil.collectElementsOfType(parsed, PsiErrorElement.class)) {
          System.out.println(file + ":" + error.getTextOffset() + ": " + error.getErrorDescription());
          errors++;
        }
      }
    } finally { Disposer.dispose(disposable); }
    System.out.println("Kotlin syntax: " + args.length + " files, " + errors + " errors. This is not a target compilation.");
    if (errors != 0) System.exit(1);
  }
}
