// Two forms the way two codebases write them: react-hook-form validated by a zod schema, and Formik
// validated by yup.
import { useState } from 'react';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { useForm, type Resolver } from 'react-hook-form';
import { z } from 'zod';
import { Formik, Form, Field, ErrorMessage } from 'formik';
import * as yup from 'yup';
import { nanoid } from 'nanoid';
import { isValidPhoneNumber } from 'libphonenumber-js';

const contact = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.email('Enter a valid email'),
  phone: z.string().refine((v) => isValidPhoneNumber(v, 'US'), 'Enter a US phone number'),
  seats: z.coerce.number().int().min(1, 'At least one seat').max(500, 'At most 500 seats'),
});
type Contact = z.infer<typeof contact>;

// What @hookform/resolvers' zodResolver does, written out.
const zodResolver: Resolver<Contact> = async (values) => {
  const result = contact.safeParse(values);
  if (result.success) return { values: result.data, errors: {} };
  const errors: Record<string, { type: string; message: string }> = {};
  for (const issue of result.error.issues) {
    const key = String(issue.path[0]);
    errors[key] ??= { type: issue.code, message: issue.message };
  }
  return { values: {}, errors: errors as never };
};

const shipping = yup.object({
  street: yup.string().required('Street is required'),
  city: yup.string().required('City is required'),
  zip: yup.string().matches(/^\d{5}$/, 'ZIP is five digits').required('ZIP is required'),
});

function ContactForm() {
  const [sent, setSent] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Contact>({ resolver: zodResolver, defaultValues: { name: '', email: '', phone: '', seats: 1 } });
  return (
    <Box component="form" onSubmit={handleSubmit((values) => setSent(`${values.name} (${nanoid(6).length} char ticket)`))} noValidate>
      <Typography variant="h6">Contact</Typography>
      <Stack spacing={1} sx={{ maxWidth: 360 }}>
        <TextField size="small" label="Name" {...register('name')} error={!!formState.errors.name} helperText={formState.errors.name?.message} />
        <TextField size="small" label="Email" {...register('email')} error={!!formState.errors.email} helperText={formState.errors.email?.message} />
        <TextField size="small" label="Phone" {...register('phone')} error={!!formState.errors.phone} helperText={formState.errors.phone?.message} />
        <TextField size="small" label="Seats" type="number" {...register('seats')} error={!!formState.errors.seats} helperText={formState.errors.seats?.message} />
        <Button type="submit" variant="contained" name="contact-submit">
          Send contact
        </Button>
      </Stack>
      {sent && <Alert severity="success">Sent for {sent}</Alert>}
      {Object.keys(formState.errors).length > 0 && <Typography>{Object.keys(formState.errors).length} problems in the contact form</Typography>}
    </Box>
  );
}

function ShippingForm() {
  return (
    <Formik initialValues={{ street: '', city: '', zip: '' }} validationSchema={shipping} onSubmit={() => undefined}>
      {({ errors, touched, isValid, dirty }) => (
        <Form>
          <Typography variant="h6">Shipping</Typography>
          <Stack spacing={1} sx={{ maxWidth: 360 }}>
            {(['street', 'city', 'zip'] as const).map((name) => (
              <div key={name}>
                <Field name={name} placeholder={name} />
                {touched[name] && errors[name] && (
                  <Typography color="error" variant="caption" component="div">
                    <ErrorMessage name={name} />
                  </Typography>
                )}
              </div>
            ))}
            <Typography variant="caption">{dirty && isValid ? 'Ready to ship' : 'Address incomplete'}</Typography>
          </Stack>
        </Form>
      )}
    </Formik>
  );
}

export default function Forms() {
  return (
    <Stack direction="row" spacing={4}>
      <ContactForm />
      <ShippingForm />
    </Stack>
  );
}
