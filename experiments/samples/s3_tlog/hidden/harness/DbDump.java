import java.io.OutputStreamWriter;
import java.io.Writer;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/**
 * Hidden-harness table dumper.
 *
 * usage: java -cp h2.jar:classes DbDump <jdbcUrl> <user> <password> <outDir> TABLE=COL1,COL2,... [...]
 *
 * Writes <outDir>/<TABLE>.csv (UTF-8, LF, header row). Rows are sorted by the full tuple of
 * formatted values (key columns are listed first in each spec), so the output is independent of
 * physical row order. Formatting is implementation-neutral:
 *   NULL -> empty field, numbers -> plain decimal with trailing zeros stripped, other -> getString().
 */
public class DbDump {

    public static void main(String[] args) throws Exception {
        if (args.length < 5) {
            System.err.println("usage: DbDump <url> <user> <password> <outDir> TABLE=COL,... ...");
            System.exit(2);
        }
        String url = args[0];
        String user = args[1];
        String password = args[2];
        Path outDir = Paths.get(args[3]);
        Files.createDirectories(outDir);
        try (Connection con = DriverManager.getConnection(url, user, password)) {
            for (int i = 4; i < args.length; i++) {
                String spec = args[i];
                int eq = spec.indexOf('=');
                String table = spec.substring(0, eq);
                String[] cols = spec.substring(eq + 1).split(",");
                dumpTable(con, table, cols, outDir.resolve(table + ".csv"));
            }
        }
    }

    private static void dumpTable(Connection con, String table, String[] cols, Path out) throws Exception {
        List<String[]> rows = new ArrayList<>();
        String sql = "SELECT " + String.join(", ", cols) + " FROM " + table;
        try (Statement st = con.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            while (rs.next()) {
                String[] row = new String[cols.length];
                for (int c = 0; c < cols.length; c++) {
                    row[c] = format(rs.getObject(c + 1));
                }
                rows.add(row);
            }
        }
        rows.sort((a, b) -> {
            for (int i = 0; i < a.length; i++) {
                String x = a[i] == null ? "" : a[i];
                String y = b[i] == null ? "" : b[i];
                int c = x.compareTo(y);
                if (c != 0) {
                    return c;
                }
            }
            return 0;
        });
        try (Writer w = new OutputStreamWriter(Files.newOutputStream(out), StandardCharsets.UTF_8)) {
            w.write(String.join(",", cols));
            w.write("\n");
            for (String[] row : rows) {
                StringBuilder sb = new StringBuilder();
                for (int c = 0; c < row.length; c++) {
                    if (c > 0) {
                        sb.append(',');
                    }
                    sb.append(csv(row[c]));
                }
                w.write(sb.toString());
                w.write("\n");
            }
        }
    }

    private static String format(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof BigDecimal) {
            return plain((BigDecimal) v);
        }
        if (v instanceof Double || v instanceof Float) {
            return plain(BigDecimal.valueOf(((Number) v).doubleValue()));
        }
        if (v instanceof Number) {
            return v.toString();
        }
        return v.toString();
    }

    private static String plain(BigDecimal d) {
        if (d.signum() == 0) {
            return "0";
        }
        return d.stripTrailingZeros().toPlainString();
    }

    private static String csv(String v) {
        if (v == null) {
            return "";
        }
        boolean quote = v.isEmpty() || v.indexOf(',') >= 0 || v.indexOf('"') >= 0 || v.indexOf('\n') >= 0
                || v.indexOf('\r') >= 0 || v.startsWith(" ") || v.endsWith(" ");
        if (!quote) {
            return v;
        }
        return "\"" + v.replace("\"", "\"\"") + "\"";
    }
}
