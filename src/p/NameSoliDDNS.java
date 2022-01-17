package p;

import javax.net.ssl.*;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.security.spec.RSAOtherPrimeInfo;

import Toolbox.ProgressBar;
import Toolbox.NowString;

public class NameSoliDDNS {

    private static final int IS_TEST = 0; // 测试为1，不在测试为0，用于代理

    /**
     * 程序入口
     *
     * @param args args[0]为密钥，args[1]为域名，不带前缀
     */
    public static void main(String[] args) {

        if (args.length == 2) {
            DNS_KEY = args[0];
            SUBDOMAIN = args[1];
        } else if (args.length == 3) {
            DNS_KEY = args[0];
            SUBDOMAIN = args[1];
            FREQUENCY = Long.valueOf(args[2]);
        } else {
            System.out.println("The program requires at least two parameters\n" +
                    "1: namesilo key; 2: domain name; optional parameter 3: the frequency of querying the local IP address (in milliseconds), the default is 600,000 milliseconds(10 min) once");
            System.exit(-1);
        }
        // 从子域名提取域名
        DNS_DOMAIN = SUBDOMAIN.substring(SUBDOMAIN.lastIndexOf('.', SUBDOMAIN.lastIndexOf('.') - 1) + 1, SUBDOMAIN.length());
        if (SUBDOMAIN.length() - DNS_DOMAIN.length() - 1 < 1) {
            NO_SUBDOMAIN = true;
            SUBDOMAIN = "";
        } else {
            SUBDOMAIN = SUBDOMAIN.substring(0, SUBDOMAIN.length() - DNS_DOMAIN.length() - 1);
        }
        // 判断操作系统，非win10不打印计时百分比,方便计入日志
        if (System.getProperty("os.name").indexOf("Windows") != -1) {
            IS_WINDOWS = true;
        }


        // 测试用
        if (IS_TEST != 0) {
            System.setProperty("http.proxyHost", "localhost");
            System.setProperty("http.proxyPort", "8080");
            System.setProperty("https.proxyHost", "localhost");
            System.setProperty("https.proxyPort", "8080");
        }

        restart();
    }

    private static String DNS_KEY;
    private static String SUBDOMAIN; // 获取域名列表中的子域名对应的RRID必须要子域名来定位
    private static boolean NO_SUBDOMAIN;
    private static boolean IS_WINDOWS = false;
    private static String DNS_DOMAIN; // 查域名列表、更新DNS只能用域名
    private static long FREQUENCY = 600000;

    private static String DNS_IP;
    private static String DNS_RRID;

    private static final String GET_IP_URL = "https://2021.ip138.com/";
    private static final String[][] GET_IP_HEAD = {
            {"Host", "2021.ip138.com"},
            {"User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0"},
            //{"Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"},
            //{"Accept-Language", "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2"},
            //{"Accept-Encoding", "gzip, deflate"},
            {"Content-Type", "application/xml;charset=UTF-8"},
            {"Connection", "close"},
            {"Referer", "https://www.ip138.com/"},
            {"Upgrade-Insecure-Requests", "1"}
    };

    private static final String API_GET_DNS_LIST_URL = "https://www.namesilo.com/api/dnsListRecords?version=1&type=xml";
    private static final String API_UPDATE_DNS_URL = "https://www.namesilo.com/api/dnsUpdateRecord?version=1&type=xml&rrttl=7207"; // rrhost即前缀，rrid这里没有给出,rrvalue即新的IP
    private static final String[][] NAMESILO_HEAD = {
            {"Host", "www.namesilo.com"},
            //{"User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0"},
            //{"Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"},
            //{"Accept-Language", "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2"},
            //{"Accept-Encoding", "gzip, deflate"},
            {"Content-Type", "application/x-www-form-urlencoded;charset=UTF-8"},
            {"Connection", "close"},
            {"Upgrade-Insecure-Requests", "1"}
    };

    /**
     * apiGetIP();
     */
    public static void init() {
        System.out.println("initializing...");
        if (apiGetIP() == -1) {
            System.out.println("initialization failed: Please check [ your namesilo key ] / [ domain name ] or [ your network ]");
            System.exit(-1);
        }
    }

    /**
     * @return 访问https://202020.ip138.com/获取到的 IP
     */
    public static String getMyIP() {
        String response = processDoGet(GET_IP_URL, GET_IP_HEAD);
        int a = response.indexOf("是：");
        int z = response.indexOf("</title>");
        if (a == -1 || z == -1) {
            System.out.println("getMyIP(): " + response);
            System.exit(-1);
        }
        String myip = response.substring(a + 2, z);
        NowString.printNow();
        System.out.println(" Get IP from 2021.ip138.com: " + myip);

        return myip;
    }

    /**
     * update DNS_IP & DNS_RRID
     *
     * @return 0 on success;
     */
    public static int apiGetIP() {
        String response = processDoGet(API_GET_DNS_LIST_URL + "&key=" + DNS_KEY + "&domain=" + DNS_DOMAIN, NAMESILO_HEAD);
        int a = 0;
        if (NO_SUBDOMAIN) {
            a = response.indexOf("<host>" + DNS_DOMAIN + "</host><value>");
        } else {
            a = response.indexOf("<host>" + SUBDOMAIN + "." + DNS_DOMAIN + "</host><value>");
        }
        if (a == -1) {
            System.out.println("apiGetIP(): " + response);
            return -1;
        }
        a=response.indexOf("</host><value>",a);
        int z = response.indexOf("</value>", a);
        DNS_IP = response.substring(a + 14, z);

        System.out.println("Get IP from NameSilo: " + DNS_IP);

        a = response.lastIndexOf("<record_id>", a);
        z = response.indexOf("</record_id>", a);
        DNS_RRID = response.substring(a + 11, z);

        return 0;
    }

    /**
     * 循环地检查IP是否有变动，有则提交
     *
     * @return
     */
    public static int loop() {
        ProgressBar bar = new ProgressBar();
        String myip = null;
        while (true) {
            myip = getMyIP();
            if (!myip.equals(DNS_IP)) {
                if (apiUpdate(myip) == -1) {
                    // github操作
                    return -1;
                }
            }


            // 暂停10分钟，打印进度条
            try {
                //bar.noBarPrint(15000);
                if (IS_WINDOWS) {
                    bar.noBarPrint(FREQUENCY);
                } else { // linux
                    // 避免sleep过久无法唤醒，这只是我的猜测，不知道现实中会不会有无法唤醒的情况
                    for (int i = 0; i < 100; i++) {
                        Thread.sleep(FREQUENCY/100);
                    }
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }


        }
    }

    /**
     * 更新DNS上的IP，更新 DNSDNS_RRID
     *
     * @param myip 要更新的IP
     * @return 不成功返回-1，其他值都是成功
     */
    public static int apiUpdate(String myip) {
        String response = processDoGet(API_UPDATE_DNS_URL + "&rrvalue=" + myip + "&rrid=" + DNS_RRID + "&key=" + DNS_KEY + "&domain=" + DNS_DOMAIN + "&rrhost=" + SUBDOMAIN, NAMESILO_HEAD);
        int a = response.lastIndexOf("<record_id>");
        if (a == -1) {
            System.out.println(response);
            return -1;
        }
        int z = response.indexOf("</record_id>", a);
        DNS_RRID = response.substring(a + 11, z);
        a = response.indexOf("</operation><ip>");
        z = response.indexOf("</ip>", a);
        DNS_IP = response.substring(a + 16, z);
        //DNS_IP=
        if (response.indexOf("<code>300</code><detail>success</detail>") != -1) {
            System.out.println("apiUpdate completed");
            return 0;
        }
        return -1;
    }

    /**
     * init();loop();
     */
    public static void restart() {
        init();
        System.exit(loop());
    }

    static class DoGetThread implements Runnable{
        public DoGetThread() {
        }

        public DoGetThread(String URL, String[][] head) {
            this.URL = URL;
            this.head = head;
        }

        private String URL;
        private String[][] head;
        private String response;

        public String getResponse() {
            return response;
        }

        @Override
        public void run() {
            response=doGet(URL,head);
        }
    }

    /**
     * api有时会导致doGet异常中断，即使catch了Exception也没用，所以用子线程来请求，避免主线程中断
     */
    public static String processDoGet(String URL, String[][] head){
        DoGetThread doGetThread = new DoGetThread(URL, head);
        Thread thread=new Thread(doGetThread);
        thread.start();
        try {
            thread.join(15000);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        if (doGetThread.getResponse()!=null)
            return doGetThread.getResponse();
        else
            return "DoGetThread Error";
    }

    /***************************************** 发送 get请求 *******************************************************/

    /**
     * @param URL
     * @param head
     * @return
     * @link https://www.jianshu.com/p/117264481886
     */
    public static String doGet(String URL, String[][] head) {
        HttpURLConnection conn = null;
        InputStream is = null;
        BufferedReader br = null;
        StringBuilder result = new StringBuilder();
        try {
            //创建远程url连接对象
            URL url = new URL(URL);

            if (IS_TEST != 0) {
                trustAllHosts();
            }
            //通过远程url连接对象打开一个连接，强转成HTTPURLConnection类
            HttpsURLConnection https = (HttpsURLConnection) url.openConnection();

            if (IS_TEST != 0) {
                https.setHostnameVerifier(DO_NOT_VERIFY);
            }

            conn = https;
            conn.setRequestMethod("GET");
            //设置连接超时时间和读取超时时间
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(50000);
            for (int i = 1; i < head.length; ++i) {
                conn.setRequestProperty(head[i][0], head[i][1]);
            }
            //发送请求
            conn.connect();
            //通过conn取得输入流，并使用Reader读取
            if (200 == conn.getResponseCode()) {
                is = conn.getInputStream();
                br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
                String line;
                while ((line = br.readLine()) != null) {
                    result.append(line);
                    //System.out.println(line);
                }
            } else {
                System.out.println("ResponseCode is an error code:" + conn.getResponseCode());
            }
        } catch (MalformedURLException e) {
            e.printStackTrace();
        } catch (IOException e) {
            // 网站超时未返回
            if (e.toString().equals("java.net.SocketTimeoutException: Read timed out")) {
                // 先关闭当前的连接资源
                try {
                    if (br != null) {
                        br.close();
                    }
                    if (is != null) {
                        is.close();
                    }
                } catch (IOException ioe) {
                    ioe.printStackTrace();
                }
                conn.disconnect();

                restart();
            }
            e.printStackTrace();
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try {
                if (br != null) {
                    br.close();
                }
                if (is != null) {
                    is.close();
                }
            } catch (IOException ioe) {
                ioe.printStackTrace();
            }
            conn.disconnect();
        }
        return result.toString();
    }

    /***************************************** 代理时信任 HTTPS 证书 *******************************************************/


    /**
     * @link https://blog.csdn.net/chaishen10000/article/details/82992291
     */
    final static HostnameVerifier DO_NOT_VERIFY = new HostnameVerifier() {
        public boolean verify(String hostname, SSLSession session) {
            return true;
        }
    };

    /**
     * Trust every server - dont check for any certificate
     */
    private static void trustAllHosts() {
        final String TAG = "trustAllHosts";
        // Create a trust manager that does not validate certificate chains
        TrustManager[] trustAllCerts = new TrustManager[]{new X509TrustManager() {
            public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                return new java.security.cert.X509Certificate[]{};
            }

            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                //Log.i(TAG, "checkClientTrusted");
            }

            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                //Log.i(TAG, "checkServerTrusted");
            }
        }};
        // Install the all-trusting trust manager
        try {
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, trustAllCerts, new java.security.SecureRandom());
            HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
        } catch (Exception e) {
            e.printStackTrace();
        }

    }

}
