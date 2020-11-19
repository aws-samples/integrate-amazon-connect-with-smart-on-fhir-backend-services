package com.amazonaws.acmpcakms.examples;

import com.amazonaws.services.acmpca.model.*;
import com.amazonaws.regions.Regions;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

import java.nio.charset.StandardCharsets;
import java.security.Security;

import java.io.FileWriter;
import java.io.*;


public class Runner {

    static {
        Security.addProvider(new BouncyCastleProvider());
    }

    public static void main(final String[] args) throws Exception {

        String ROOT_COMMON_NAME = null;
        String END_ENTITY_COMMON_NAME = null;
        String CMK_ALIAS = null;
        String REGION_OPTION = null;
        Regions region = null;

        BufferedReader in=new BufferedReader(new InputStreamReader(System.in));
        while (ROOT_COMMON_NAME==null) {
            System.out.println("Please provide the private CA root common name:");
            ROOT_COMMON_NAME = in.readLine();
        }

        while (END_ENTITY_COMMON_NAME==null) {
            System.out.println("Please provide the end entity common name:");
            END_ENTITY_COMMON_NAME = in.readLine();
        }

        while (CMK_ALIAS==null) {
            System.out.println("Please provide the alias for KMS Customer Master Key:");
            CMK_ALIAS = in.readLine();
        }

        while (REGION_OPTION==null || region==null) {
            System.out.println("Please select the AWS Region to deploy KMS Customer Master Key and Private CA:");
            System.out.println("[1] => us east 1");
            System.out.println("[2] => us east 2");
            System.out.println("[3] => us west 1");
            System.out.println("[4] => us west 2");
            System.out.println("[5] => eu west 1");
            System.out.println("[6] => eu west 2");
            System.out.println("[7] => eu west 3");
            System.out.println("[8] => eu north 1");
            System.out.println("[9] => eu central 1");
            System.out.println("[10] => ca central 1");
            REGION_OPTION = in.readLine();
            int selection = Integer.parseInt(REGION_OPTION);
            switch(selection) {
                case 1:
                    region = Regions.US_EAST_1;
                    break;
                case 2:
                    region = Regions.US_EAST_2;
                    break;
                case 3:
                    region = Regions.US_WEST_1;
                    break;
                case 4:
                    region = Regions.US_WEST_2;
                    break;
                case 5:
                    region = Regions.EU_WEST_1;
                    break;
                case 6:
                    region = Regions.EU_WEST_2;
                    break;
                case 7:
                    region = Regions.EU_WEST_3;
                    break;
                case 8:
                    region = Regions.EU_NORTH_1;
                    break;
                case 9:
                    region = Regions.EU_CENTRAL_1;
                    break;
                case 10:
                    region = Regions.CA_CENTRAL_1;
                    break;
                default:
                    region = Regions.US_EAST_1;
            }
        }

        /* Creating a CA hierarcy in ACM Private CA. This CA hiearchy consistant of a Root and subordinate CA */
        System.out.println("Creating a CA hierarchy\n");

        PrivateCA rootPrivateCA = PrivateCA.builder()
                .withCommonName(ROOT_COMMON_NAME)
                .withType(CertificateAuthorityType.ROOT)
                .withRegion(region)
                .getOrCreate();

        /* Creating a asymmetric key pair using AWS KMS */
        System.out.println();
        System.out.println("Creating a asymmetric key pair using AWS KMS\n");

        AsymmetricCMK codeSigningCMK = AsymmetricCMK.builder()
                .withAlias(CMK_ALIAS)
                .withRegion(region)
                .getOrCreate();

        /* Creating a asymmetric key pair using AWS KMS */
        System.out.println();
        System.out.println("Creating a CSR(Certificate signing request) for creating a code signing certificate\n");
        String codeSigningCSR = codeSigningCMK.generateCSR(END_ENTITY_COMMON_NAME);

        /* Issuing the code signing certificate from ACM Private CA */
        System.out.println();
        System.out.println("Issuing a code signing certificate from ACM Private CA\n");
        GetCertificateResult codeSigningCertificate = rootPrivateCA.issueCodeSigningCertificate(codeSigningCSR);

        FileWriter myWriter = new FileWriter("myappcodesigningcertificate.pem");
        myWriter.write(codeSigningCertificate.getCertificate());
        myWriter.close();
    }
}
