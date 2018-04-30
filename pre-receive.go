package main

import (
	"bufio"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"
	"unicode/utf8"
)

var logger = log.New(os.Stderr, "", 0)
var deployerEmail, _ = callGitCmd("git config --system user.email")
var errProtectBranchMaster = errors.New("Branch master is protected, no one can delete or force push")
var errProtectReleaseTag = errors.New("The release tag is protected, no one can delete or force push")
var errProtectReleaseBranch = errors.New("The release branch tagged, no one can delete or force push except that you merge it to the master branch")

func abort(err error) {
	os.Exit(1)
}

func isNullCommit(commitID string) bool {
	return strings.Repeat("0", utf8.RuneCountInString(commitID)) == commitID
}

func callGitCmd(command string) (string, error) {
	cmd := exec.Command("sh", "-c", command)
	out, err := cmd.Output()
	return strings.TrimSpace(string(out)), err
}

func getMergeBaseCommit(ref1, ref2 string) (string, error) {
	cmd := fmt.Sprintf("git merge-base %s %s", ref1, ref2)
	return callGitCmd(cmd)
}

func isForcePush(oldCommitID, newCommitID string) bool {
	cmd := fmt.Sprintf("git merge-base %s %s", oldCommitID, newCommitID)
	mergeBase, err := callGitCmd(cmd)
	if err != nil {
		return true
	}
	return mergeBase != oldCommitID
}

func isBranchCheckoutFromMaster(branchRef string) bool {
	_, err := getMergeBaseCommit(branchRef, "refs/heads/master")
	return err == nil
}

func isBranchMergeToMaster(branchRef string) bool {
	mergeBaseID, _ := getMergeBaseCommit(branchRef, "refs/heads/master")
	branchLastCommitID, _ := callGitCmd(fmt.Sprintf("git rev-parse %s", branchRef))
	return mergeBaseID == branchLastCommitID
}

func isSomeoneTag(ref, email string) bool {
	cmd := fmt.Sprintf("git for-each-ref --format='%%(objecttype) %%(taggeremail)' %s", ref)
	out, _ := callGitCmd(cmd)
	output := strings.Split(out, " ")
	if output[0] != "tag" {
		return false
	}
	return output[1][1:len(output[1])-1] == email
}

func findLastTagCommitID(oldCommitID, newCommitID, email string) string {
	out, _ := callGitCmd(fmt.Sprintf("git log --pretty='%%H %%d' --decorate=full %s..%s", oldCommitID, newCommitID))
	outputs := strings.Split(out, "\n")
	for _, line := range outputs {
		if strings.Contains(line, "refs/tags/") {
			s := strings.SplitN(line, " ", 2)
			commitID, tagText := s[0], s[1]
			tagText = tagText[7 : len(tagText)-1]
			for _, tag := range strings.Split(tagText, " ") {
				if !strings.HasPrefix(tag, "refs/tags/") {
					continue
				}
				tag = strings.Trim(tag, ",")
				if isSomeoneTag(tag, email) {
					return commitID
				}
			}
		}
	}
	return ""
}

func protectMasterBranch(oldCommitID, newCommitID string) error {
	if isNullCommit(oldCommitID) {
		return nil
	}
	if isNullCommit(newCommitID) {
		return errProtectBranchMaster
	}
	if isForcePush(oldCommitID, newCommitID) {
		return errProtectBranchMaster
	}
	return nil
}

func protectReleaseTag(oldCommitID, newCommitID, ref string) error {
	if isNullCommit(oldCommitID) {
		return nil
	}
	if isNullCommit(newCommitID) || oldCommitID != newCommitID {
		if isSomeoneTag(ref, deployerEmail) {
			return errProtectReleaseTag
		}
	}
	return nil
}

func protectReleaseBranch(oldCommitID, newCommitID, ref string) error {
	if isNullCommit(oldCommitID) {
		if isBranchCheckoutFromMaster(newCommitID) {
			return nil
		}
		return errProtectReleaseBranch
	}
	if isNullCommit(newCommitID) || isForcePush(oldCommitID, newCommitID) {
		mergeBaseCommitID, _ := getMergeBaseCommit(ref, "refs/heads/master")
		lastDeployerTagCommitID := findLastTagCommitID(mergeBaseCommitID, ref, deployerEmail)
		if lastDeployerTagCommitID == "" {
			return nil
		}
		if !isBranchMergeToMaster(lastDeployerTagCommitID) {
			return errProtectReleaseBranch
		}
	}
	return nil
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		s := strings.Split(scanner.Text(), " ")
		oldCommitID, newCommitID, ref := s[0], s[1], s[2]
		switch {
		case strings.HasPrefix(ref, "refs/heads/master"):
			if err := protectMasterBranch(oldCommitID, newCommitID); err != nil {
				abort(err)
			}
		case strings.HasPrefix(ref, "refs/tags/"):
			if err := protectReleaseTag(oldCommitID, newCommitID, ref); err != nil {
				abort(err)
			}
		case strings.HasPrefix(ref, "refs/heads/release/"):
			if err := protectReleaseBranch(oldCommitID, newCommitID, ref); err != nil {
				abort(err)
			}
		}
	}
}
