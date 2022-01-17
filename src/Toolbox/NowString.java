package Toolbox;

import java.text.SimpleDateFormat;
import java.util.Date;

/**
 * @author Edit by 云牧青
 * @link <a href="https://www.cnblogs.com/yelanggu/p/10876872.html" > 出处 </a>
 */
public class NowString {
    public static void printNow() {
        SimpleDateFormat df = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");//设置日期格式
        System.out.print(df.format(new Date()));// new Date()为获取当前系统时间
    }
}
