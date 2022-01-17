package Toolbox;

/**
 * @author Edit by 云牧青
 * @link <a href="https://www.jb51.net/article/186541.htm" > 出处 </a>
 */
public class ProgressBar {
    public static void main(String[] args) {

    }


    private int index = 0;
    private String finish;
    private String unFinish;


    // 进度条粒度
    private final int PROGRESS_SIZE = 50;
    private int BITE = 2;

    private String getNChar(int num, char ch){
        StringBuilder builder = new StringBuilder();
        for(int i = 0; i < num; i++){
            builder.append(ch);
        }
        return builder.toString();
    }

    /**
     * 阻塞式打印进度条，时间固定
     * @param millis 整个进度条读完需要的时间
     * @throws InterruptedException
     */
    public void printProgress(long millis) throws InterruptedException {
        System.out.print("Progress:");
        int len;

        finish = getNChar(index / BITE, '=');
        unFinish = getNChar(PROGRESS_SIZE - index / BITE, ' ');
        String target = String.format("%3d%%[%s%s]100%%", index, finish, unFinish);
        System.out.print(target);
        len=target.length();

        while (index <= 100){
            finish = getNChar(index / BITE, '=');
            unFinish = getNChar(PROGRESS_SIZE - index / BITE, ' ');

            target = String.format("%3d%%├%s%s┤100%%", index, finish, unFinish);
            System.out.print(getNChar(len, '\b'));
            System.out.print(target);
            len=target.length();

            Thread.sleep(millis/100);
            index++;
        }
        index=0;
        System.out.print(getNChar(len+"Progress:".length(), '\b'));
    }

    /**
     * 打印进度（带休眠），仅有数字和百分号，因为进度条在某些电脑上有 bug
     *
     * @param millis
     * @throws InterruptedException
     */
    public void noBarPrint(long millis) throws InterruptedException {
        System.out.print("Progress:");
        int len;

        String target = String.format("%3d%%", index);
        System.out.print(target);
        len=target.length();

        while (index <= 100){

            target = String.format("%3d%%", index);
            System.out.print(getNChar(len, '\b'));
            System.out.print(target);
            len=target.length();

            Thread.sleep(millis/100);
            index++;
        }
        index=0;
        System.out.print(getNChar(len+"Progress:".length(), '\b'));
    }
}
