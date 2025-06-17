#!/bin/bash

# Set iDRAC credentials and IP
IDRAC_IP="10.20.30.250"
PASS_FILE="$HOME/.ssh/idrac_pass"
SSH_CMD="sshpass -f $PASS_FILE ssh -o StrictHostKeyChecking=no root@$IDRAC_IP"

# Function to display menu
show_menu() {
    clear
    echo "============================"
    echo " Dell iDRAC Management Menu"
    echo "============================"
    echo "1) Power Cycle (Reboot Server)"
    echo "2) Power Off Server"
    echo "3) Power On Server"
    echo "4) Check Power Status"
    echo "5) Reset iDRAC (Fix Web UI Login Issues)"
    echo "6) Exit"
    echo "7) Hard Reset (Force Reboot)"
    echo "8) Show System Information"
    echo "9) View System Event Log"
    echo "10) View Sensor Readings (Temps/Fans/PSU)"
    echo "11) View Job Queue"
    echo "12) Collect Tech Support Report (TSR)"
    echo "13) RAID Physical Disk Info"

    echo "============================"
    read -p "Enter your choice [1-13]: " choice
}

# Function to execute selected command
execute_choice() {
    case $choice in
        1)
            echo "Rebooting the server via iDRAC..."
            $SSH_CMD racadm serveraction powercycle
            ;;
        2)
            echo "Shutting down the server (force off)..."
            $SSH_CMD racadm serveraction powerdown
            ;;
        3)
            echo "Powering on the server..."
            $SSH_CMD racadm serveraction powerup
            ;;
        4)
            echo "Checking power status..."
            $SSH_CMD racadm serveraction powerstatus | grep --color -e ON -e OFF
            ;;
        5)
            echo "Resetting iDRAC (this may take a few minutes)..."
            $SSH_CMD racadm racreset
            echo "iDRAC is resetting. Wait a few minutes before accessing the web UI."
            ;;
        6)
            echo "Exiting."
            exit 0
            ;;
        7)
            echo "Performing a HARD reset (cold reboot)..."
            $SSH_CMD racadm serveraction hardreset
            ;;
        8)
            echo "System information:"
            $SSH_CMD racadm getsysinfo
            ;;
        9)
            echo "System Event Log (SEL):"
            $SSH_CMD racadm getsel | less   # pipe to less for paging
            ;;
        10)
            echo "Live sensor readings:"
            $SSH_CMD racadm getsensorinfo
            ;;
        11)
            echo "Lifecycle-Controller Job Queue:"
            $SSH_CMD racadm jobqueue view
            ;;
        12)
            echo "Collecting Tech-Support Report (may take several minutes)..."
            JOBID=$($SSH_CMD racadm techsupreport collect -t SysInfo,TTYLog | awk '/JID_/ {print $NF}')
            echo "TSR collection started (Job ID: $JOBID). Track progress with option 11."
            ;;
        13)
            echo "RAID physical-disk information:"
            $SSH_CMD racadm raid get pdisks -o | less
            ;;
        *)
            echo "Invalid choice, please try again."
            ;;
    esac
}

# Main loop
while true; do
    show_menu
    execute_choice
    read -p "Press Enter to continue..." dummy
done

