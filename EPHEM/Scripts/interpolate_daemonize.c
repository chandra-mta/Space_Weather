/*
* interpolate_daemonize.c
* daemon for ephem interpolate python script
* sleeps 30 seconds after each process completed before starting the next
*
* Ref: https://stackoverflow.com/questions/17954432/creating-a-daemon-in-linux
*
*   author: t. isobe (tisobe@cfa.harvard.edu)
*   last update: Jan 29, 2019
*/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <syslog.h>

static void skeleton_daemon()
{
    pid_t pid, sid;

    /* Fork off the parent process */
    pid = fork();

    /* An error occurred */
    if (pid < 0)
        exit(EXIT_FAILURE);

    /* Success: Let the parent terminate */
    if (pid > 0)
        exit(EXIT_SUCCESS);

    /* On success: The child process becomes session leader */
    sid = setsid();
    if (sid < 0)
        exit(EXIT_FAILURE);

    /* Catch, ignore and handle signals */
    signal(SIGCHLD, SIG_IGN);
    signal(SIGHUP,  SIG_IGN);

    /* Fork off for the second time*/
    pid = fork();

    /* An error occurred */
    if (pid < 0)
        exit(EXIT_FAILURE);

    /* Success: Let the parent terminate */
    if (pid > 0)
        exit(EXIT_SUCCESS);

    /* Set new file permissions */
    umask(0);

    /* Change the working directory to the root directory */
    /* or another appropriated directory */
    if((chdir("/data/mta/Script/SOH"))< 0) {
        exit(EXIT_FAILURE);
    }

    /* we are ignoring all system log part as we don't have a permission to */
    /* write on /var/log directory                                          */

    /* Close all open file descriptors */
    /*
    int x;
    for (x = sysconf(_SC_OPEN_MAX); x>=0; x--)
    {
        close (x);
    }
    */

    /* Open the log file */
    /*
	setlogmask (LOG_UPTO (LOG_NOTICE));
    openlog ("./log_sh_all", LOG_PID, LOG_DAEMON); 
    */

}

/*---------------------------------------------------------------------------------*/
/*---------------------------------------------------------------------------------*/
/*---------------------------------------------------------------------------------*/

int main()
{
    skeleton_daemon();
    FILE *fp, *fo;
    char path[1035];

    while(1)
    {
        /* run the shell script for all pages. this checks whther previous */
        /* prcoess is still running before starting a new process.         */

        fp = popen("/data/mta4/Space_Weather/EPHEM/Scripts/interpolate_script.sh", "r");

        /* check the script runs correctly */

        if (fp == NULL){
            fo  = fopen("/data/mta4/Space_Weather/EPHEM/Scripts/interpolate_log", "w");
            fprintf(fo, "Failed to run all SOH process\n");
            fclose(fo);
            break;
        }else{

        /* update the log file --- this is used to see whether the process is still running */

            fo  = fopen("/data/mta4/Space_Weather/EPHEM/Scripts/interpolate_log", "w");
            while (fgets(path, sizeof(path)-1, fp) != NULL) {
                fprintf(fo, path);
            }
            fclose(fo);
        }

        pclose(fp);

        /* sleep 180 seconds before starting the new round */

        sleep(180);
    }

    /* if the daemon process died, send email to admin */

    fo = fopen("./zspace", "w");
    fprintf(fo, "Ephem Interpolate daemon stopped. Restart the process:\n\n");
    fprintf(fo, "\t\tnohup /data/mta4/Space_Weather/EPHEM/Scripts/interpolate_daemonize &\n\n");
    fprintf(fo, "This process should be run on luke-v as mta.\n");
    fclose(fo);

    system("cat ./zspace |mailx -s 'Ephem Interpolate daemon stopped' tisobe@cfa.harvard.edu");
    system("rm -rf ./zsapce");

    return EXIT_SUCCESS;
}
